"""Offline model tests; no model weights or network access are required."""
import sys
from types import SimpleNamespace

import pytest

from app.ai import offline_client


def test_model_path_defaults_to_homer_models(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("HOMER_OFFLINE_MODEL_PATH", raising=False)
    assert offline_client.model_path() == (
        tmp_path / ".homer" / "models" / offline_client.DEFAULT_FILE
    )


def test_custom_model_path_is_respected(monkeypatch, tmp_path):
    target = tmp_path / "custom.gguf"
    monkeypatch.setenv("HOMER_OFFLINE_MODEL_PATH", str(target))
    assert offline_client.model_path() == target


def test_generate_reply_uses_small_bounded_chat_completion(monkeypatch):
    class FakeModel:
        def __init__(self):
            self.kwargs = None

        def create_chat_completion(self, **kwargs):
            self.kwargs = kwargs
            return {"choices": [{"message": {"content": "Hello from offline HOMER."}}]}

    fake = FakeModel()
    monkeypatch.setattr(offline_client, "_load_model", lambda: fake)
    reply = offline_client.generate_reply(
        "Hello", [{"role": "user", "content": "Earlier question"}],
        "Reference: local project notes", 999,
    )
    assert reply == "Hello from offline HOMER."
    assert fake.kwargs["max_tokens"] == 256
    assert fake.kwargs["messages"][0]["role"] == "system"
    assert "local reference excerpts" in fake.kwargs["messages"][1]["content"].lower()
    assert fake.kwargs["messages"][-1] == {"role": "user", "content": "Hello"}
    assert "tools" not in fake.kwargs


def test_generate_reply_uses_default_token_cap(monkeypatch):
    class FakeModel:
        def create_chat_completion(self, **kwargs):
            assert kwargs["max_tokens"] == 160
            return {"choices": [{"message": {"content": "Short answer."}}]}

    monkeypatch.setattr(offline_client, "_load_model", lambda: FakeModel())
    assert offline_client.generate_reply("Hi") == "Short answer."


def test_empty_offline_reply_returns_safe_message(monkeypatch):
    class FakeModel:
        def create_chat_completion(self, **kwargs):
            return {"choices": [{"message": {"content": ""}}]}

    monkeypatch.setattr(offline_client, "_load_model", lambda: FakeModel())
    assert "couldn't generate" in offline_client.generate_reply("Hi").lower()


def test_model_status_reports_missing_model_without_loading(monkeypatch, tmp_path):
    model = tmp_path / "missing.gguf"
    monkeypatch.setattr(offline_client, "model_path", lambda: model)
    status = offline_client.model_status()
    assert status["model_downloaded"] is False
    assert status["gpu_required"] is False
    assert status["context_tokens"] == 1536
    assert status["threads"] == 2
    assert status["batch_size"] == 32
    assert status["minimum_available_ram_mb"] == 900


def test_unload_model_closes_and_releases_cached_instance(monkeypatch):
    class FakeModel:
        closed = False

        def close(self):
            self.closed = True

    fake = FakeModel()
    monkeypatch.setattr(offline_client, "_model", fake)
    monkeypatch.setattr(offline_client, "_model_path", offline_client.Path("model.gguf"))
    offline_client.unload_model()
    assert fake.closed is True
    assert offline_client._model is None
    assert offline_client._model_path is None


def test_low_available_ram_is_rejected_before_loading_runtime(monkeypatch, tmp_path):
    import psutil

    model_file = tmp_path / "offline.gguf"
    with model_file.open("wb") as handle:
        handle.truncate(100_000_001)
    monkeypatch.setattr(offline_client, "model_path", lambda: model_file)
    monkeypatch.setenv("HOMER_OFFLINE_MIN_AVAILABLE_RAM_MB", "900")
    monkeypatch.setattr(
        psutil, "virtual_memory",
        lambda: type("Memory", (), {"available": 800 * 1024 * 1024})(),
    )
    with pytest.raises(RuntimeError, match="at least 900 MB free"):
        offline_client._load_model()


def test_model_loader_uses_low_memory_cpu_configuration(monkeypatch, tmp_path):
    model_file = tmp_path / "offline.gguf"
    with model_file.open("wb") as handle:
        handle.truncate(100_000_001)
    captured = {}

    class FakeLlama:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(offline_client, "model_path", lambda: model_file)
    monkeypatch.setenv("HOMER_OFFLINE_CONTEXT_TOKENS", "1536")
    monkeypatch.setenv("HOMER_OFFLINE_THREADS", "2")
    monkeypatch.setenv("HOMER_OFFLINE_BATCH_SIZE", "32")
    monkeypatch.setitem(sys.modules, "llama_cpp", SimpleNamespace(Llama=FakeLlama))
    monkeypatch.setattr(
        "psutil.virtual_memory",
        lambda: type("Memory", (), {"available": 2 * 1024 * 1024 * 1024})(),
    )
    offline_client.reset_model_for_tests()
    try:
        offline_client._load_model()
        assert captured["n_ctx"] == 1536
        assert captured["n_threads"] == 2
        assert captured["n_batch"] == 32
        assert captured["n_gpu_layers"] == 0
        assert captured["use_mmap"] is True
    finally:
        offline_client.reset_model_for_tests()
