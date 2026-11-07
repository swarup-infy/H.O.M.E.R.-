"""Online-first fallback routing tests without network calls or model weights."""
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.ai import groq_client


class TemporaryProviderError(Exception):
    status_code = 503


class AuthenticationProviderError(Exception):
    status_code = 401


class FakeCompletion:
    def __init__(self, error):
        self.error = error

    async def create(self, **kwargs):
        raise self.error


class FakeGroqClient:
    def __init__(self, error):
        self.chat = SimpleNamespace(completions=FakeCompletion(error))
        self.closed = False

    async def close(self):
        self.closed = True


def settings(**overrides):
    values = {
        "groq_api_key": "configured-test-key",
        "groq_model": "test-online-model",
        "groq_timeout_seconds": 2.0,
        "groq_max_retries": 0,
        "groq_temperature": 0.2,
        "groq_top_p": 1.0,
        "groq_reasoning_effort": "low",
        "groq_max_output_tokens": 100,
        "chat_history_messages": 12,
        "offline_fallback_enabled": True,
        "ai_mode": "auto",
        "offline_max_tokens": 120,
        "offline_threads": 2,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture(autouse=True)
def reset_persistent_groq_client():
    """Keep the module-level HTTP pool isolated between tests."""
    groq_client._groq_client = None
    groq_client._groq_client_config = None
    yield
    groq_client._groq_client = None
    groq_client._groq_client_config = None


def test_network_failure_uses_local_model_and_closes_online_client(monkeypatch):
    client = FakeGroqClient(ConnectionError("network is offline"))
    monkeypatch.setattr(groq_client, "get_settings", lambda: settings())
    monkeypatch.setattr(groq_client, "AsyncGroq", lambda **kwargs: client)
    monkeypatch.setattr(groq_client, "search_knowledge", lambda *args, **kwargs: [])
    monkeypatch.setattr(groq_client, "build_knowledge_context", lambda results: "")
    with patch("app.ai.offline_client.generate_reply", return_value="I can still help locally.") as local:
        reply = asyncio.run(groq_client.ask_homer("What is Python?"))
    assert reply.startswith("Offline mode (local AI):")
    assert "help locally" in reply
    local.assert_called_once()
    assert client.closed is False  # Keep the connection pool for the next request.
    asyncio.run(groq_client.close_ai_client())
    assert client.closed is True
    assert groq_client._last_provider == "offline"


def test_provider_server_failure_uses_local_model(monkeypatch):
    client = FakeGroqClient(TemporaryProviderError("provider unavailable"))
    monkeypatch.setattr(groq_client, "get_settings", lambda: settings())
    monkeypatch.setattr(groq_client, "AsyncGroq", lambda **kwargs: client)
    monkeypatch.setattr(groq_client, "search_knowledge", lambda *args, **kwargs: [])
    monkeypatch.setattr(groq_client, "build_knowledge_context", lambda results: "")
    with patch("app.ai.offline_client.generate_reply", return_value="Local reply"):
        reply = asyncio.run(groq_client.ask_homer("Explain electricity"))
    assert "Local reply" in reply


def test_authentication_error_does_not_switch_to_offline(monkeypatch):
    client = FakeGroqClient(AuthenticationProviderError("bad API key"))
    monkeypatch.setattr(groq_client, "get_settings", lambda: settings())
    monkeypatch.setattr(groq_client, "AsyncGroq", lambda **kwargs: client)
    with patch("app.ai.offline_client.generate_reply") as local:
        with pytest.raises(RuntimeError, match="AI provider request failed"):
            asyncio.run(groq_client.ask_homer("What is Python?"))
    local.assert_not_called()
    assert client.closed is False
    asyncio.run(groq_client.close_ai_client())
    assert client.closed is True


def test_rate_limit_does_not_switch_to_offline(monkeypatch):
    error = Exception("rate limited")
    error.status_code = 429
    client = FakeGroqClient(error)
    monkeypatch.setattr(groq_client, "get_settings", lambda: settings())
    monkeypatch.setattr(groq_client, "AsyncGroq", lambda **kwargs: client)
    with patch("app.ai.offline_client.generate_reply") as local:
        with pytest.raises(RuntimeError):
            asyncio.run(groq_client.ask_homer("What is Python?"))
    local.assert_not_called()
    asyncio.run(groq_client.close_ai_client())
    assert client.closed is True


def test_missing_key_uses_offline_only_when_groq_host_is_unreachable(monkeypatch):
    monkeypatch.setattr(groq_client, "get_settings", lambda: settings(groq_api_key=""))
    monkeypatch.setattr("app.ai.offline_client.internet_available", lambda: False)
    monkeypatch.setattr(groq_client, "search_knowledge", lambda *args, **kwargs: [])
    monkeypatch.setattr(groq_client, "build_knowledge_context", lambda results: "")
    with patch("app.ai.offline_client.generate_reply", return_value="Offline with no key"):
        reply = asyncio.run(groq_client.ask_homer("Hello"))
    assert "Offline with no key" in reply


def test_missing_key_uses_local_model_with_internet_available(monkeypatch):
    monkeypatch.setattr(groq_client, "get_settings", lambda: settings(groq_api_key=""))
    monkeypatch.setattr(groq_client, "search_knowledge", lambda *args, **kwargs: [])
    monkeypatch.setattr(groq_client, "build_knowledge_context", lambda results: "")
    with patch("app.ai.offline_client.generate_reply", return_value="Local reply"):
        reply = asyncio.run(groq_client.ask_homer("Hello"))
    assert "Local reply" in reply


def test_fallback_disabled_keeps_provider_error(monkeypatch):
    client = FakeGroqClient(ConnectionError("network down"))
    monkeypatch.setattr(groq_client, "get_settings", lambda: settings(offline_fallback_enabled=False))
    monkeypatch.setattr(groq_client, "AsyncGroq", lambda **kwargs: client)
    with patch("app.ai.offline_client.generate_reply") as local:
        with pytest.raises(RuntimeError):
            asyncio.run(groq_client.ask_homer("Hello"))
    local.assert_not_called()



def test_missing_key_uses_offline_even_when_internet_is_available(monkeypatch):
    monkeypatch.setattr(groq_client, "get_settings", lambda: settings(groq_api_key=""))
    monkeypatch.setattr(groq_client, "search_knowledge", lambda *args, **kwargs: [])
    monkeypatch.setattr(groq_client, "build_knowledge_context", lambda results: "")
    with patch("app.ai.offline_client.generate_reply", return_value="Local model works") as local:
        reply = asyncio.run(groq_client.ask_homer("Hello"))
    assert "Local model works" in reply
    local.assert_called_once()


def test_explicit_offline_mode_never_creates_groq_client(monkeypatch):
    monkeypatch.setattr(groq_client, "get_settings", lambda: settings(ai_mode="offline", groq_api_key="configured-test-key"))
    monkeypatch.setattr(groq_client, "search_knowledge", lambda *args, **kwargs: [])
    monkeypatch.setattr(groq_client, "build_knowledge_context", lambda results: "")
    with patch("app.ai.offline_client.generate_reply", return_value="Offline only") as local:
        with patch.object(groq_client, "AsyncGroq", side_effect=AssertionError("Groq must not be called")):
            reply = asyncio.run(groq_client.ask_homer("Hello"))
    assert "Offline only" in reply
    local.assert_called_once()
