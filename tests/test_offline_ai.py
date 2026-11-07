"""Offline fallback tests; all model inference and provider calls are mocked."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.ai import groq_client, offline_model


class FakeSettings:
    groq_api_key = "test-key"
    groq_model = "test-groq-model"
    groq_temperature = 0.2
    groq_top_p = 1.0
    groq_reasoning_effort = "medium"
    groq_max_output_tokens = 128
    groq_timeout_seconds = 2.0
    groq_max_retries = 0
    chat_history_messages = 12
    max_message_chars = 2000
    offline_fallback_enabled = True


def test_offline_model_status_does_not_load_optional_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("HOMER_OFFLINE_MODEL_PATH", str(tmp_path / "missing.gguf"))
    status = offline_model.model_status()
    assert status["ready"] is False
    assert status["runtime"] == "llama.cpp CPU"


def test_temporary_network_errors_trigger_fallback():
    class APIConnectionError(Exception):
        pass

    class APITimeoutError(Exception):
        pass

    class RateLimitError(Exception):
        status_code = 429

    class ServerError(Exception):
        status_code = 503

    assert groq_client._is_temporary_provider_failure(APIConnectionError())
    assert groq_client._is_temporary_provider_failure(APITimeoutError())
    assert groq_client._is_temporary_provider_failure(RateLimitError())
    assert groq_client._is_temporary_provider_failure(ServerError())


def test_authentication_and_invalid_model_errors_do_not_trigger_fallback():
    class AuthenticationError(Exception):
        status_code = 401

    class BadRequestError(Exception):
        status_code = 400

    assert not groq_client._is_temporary_provider_failure(AuthenticationError())
    assert not groq_client._is_temporary_provider_failure(BadRequestError())


def test_missing_groq_key_uses_local_fallback():
    settings = FakeSettings()
    settings.groq_api_key = ""
    with (
        patch.object(groq_client, "get_settings", return_value=settings),
        patch.object(groq_client, "_ask_offline", new=AsyncMock(return_value="Offline reply")) as fallback,
    ):
        reply = asyncio.run(groq_client.ask_homer("Explain Python lists"))
    assert reply == "Offline reply"
    fallback.assert_awaited_once_with("Explain Python lists")


def test_groq_connection_failure_switches_to_local_fallback():
    class APIConnectionError(Exception):
        pass

    class FakeCompletions:
        async def create(self, **_kwargs):
            raise APIConnectionError("network unavailable")

    class FakeClient:
        chat = SimpleNamespace(completions=FakeCompletions())

        async def close(self):
            return None

    settings = FakeSettings()
    with (
        patch.object(groq_client, "get_settings", return_value=settings),
        patch.object(groq_client, "AsyncGroq", return_value=FakeClient()),
        patch.object(groq_client, "search_knowledge", return_value=[]),
        patch.object(groq_client, "_ask_offline", new=AsyncMock(return_value="Local answer")) as fallback,
    ):
        reply = asyncio.run(groq_client.ask_homer("What is a Python dictionary?"))
    assert reply == "Local answer"
    fallback.assert_awaited_once_with("What is a Python dictionary?")


def test_groq_authentication_failure_does_not_switch_to_offline():
    class AuthenticationError(Exception):
        status_code = 401

    class FakeCompletions:
        async def create(self, **_kwargs):
            raise AuthenticationError("invalid key")

    class FakeClient:
        chat = SimpleNamespace(completions=FakeCompletions())

        async def close(self):
            return None

    with (
        patch.object(groq_client, "get_settings", return_value=FakeSettings()),
        patch.object(groq_client, "AsyncGroq", return_value=FakeClient()),
        patch.object(groq_client, "search_knowledge", return_value=[]),
        patch.object(groq_client, "_ask_offline", new=AsyncMock()) as fallback,
        pytest.raises(RuntimeError, match="Authentication and invalid-model errors"),
    ):
        asyncio.run(groq_client.ask_homer("What is a Python dictionary?"))
    fallback.assert_not_awaited()


def test_local_model_uses_rag_and_offline_limitations():
    settings = FakeSettings()
    captured = {}

    def fake_generate(messages):
        captured["messages"] = messages
        return "A local response."

    with (
        patch.object(groq_client, "get_settings", return_value=settings),
        patch.object(offline_model, "model_status", return_value={"ready": True}),
        patch.object(offline_model, "generate_reply", side_effect=fake_generate),
        patch.object(groq_client, "search_knowledge", return_value=[]),
    ):
        reply = asyncio.run(groq_client._ask_offline("Explain local RAG"))

    assert reply == "A local response."
    assert "OFFLINE MODE LIMITATIONS" in captured["messages"][0]["content"]
    assert captured["messages"][-1] == {"role": "user", "content": "Explain local RAG"}


def test_offline_fallback_can_be_disabled():
    settings = FakeSettings()
    settings.offline_fallback_enabled = False
    with (
        patch.object(groq_client, "get_settings", return_value=settings),
        pytest.raises(groq_client.AIProviderNotConfigured, match="fallback is disabled"),
    ):
        asyncio.run(groq_client._ask_offline("Hello"))


def test_offline_model_requires_a_download_before_first_use(monkeypatch, tmp_path):
    monkeypatch.setenv("HOMER_OFFLINE_MODEL_PATH", str(tmp_path / "missing.gguf"))
    with pytest.raises(offline_model.OfflineModelUnavailable, match="not installed"):
        offline_model._load_model()
