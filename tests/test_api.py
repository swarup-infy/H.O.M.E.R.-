"""API contract tests; no live Groq request or desktop action is performed."""
from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


def test_health_does_not_expose_api_key(monkeypatch) -> None:
    class FakeSettings:
        llm_provider = "groq"
        groq_api_key = "a-secret-test-key"
        groq_model = "test-model"

    monkeypatch.setattr(main, "get_settings", lambda: FakeSettings())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "provider": "groq",
        "model": "test-model",
        "api_key_configured": True,
    }
    assert "a-secret-test-key" not in response.text


def test_chat_returns_mocked_reply(monkeypatch) -> None:
    async def fake_ask_homer(message: str) -> str:
        assert message == "Hello HOMER"
        return "Hello!"

    monkeypatch.setattr(main, "ask_homer", fake_ask_homer)
    response = client.post("/chat", json={"message": "Hello HOMER"})

    assert response.status_code == 200
    assert response.json() == {"reply": "Hello!"}


def test_chat_rejects_blank_message(monkeypatch) -> None:
    async def should_not_run(_message: str) -> str:
        raise AssertionError("AI provider should not be called for a blank message")

    monkeypatch.setattr(main, "ask_homer", should_not_run)
    response = client.post("/chat", json={"message": "   "})

    assert response.status_code == 422


def test_chat_rejects_extra_fields() -> None:
    response = client.post("/chat", json={"message": "Hello", "admin": True})
    assert response.status_code == 422


def test_chat_rejects_overlong_message() -> None:
    response = client.post("/chat", json={"message": "x" * 2001})
    assert response.status_code == 422


def test_chat_reports_missing_provider_configuration(monkeypatch) -> None:
    async def missing_key(_message: str) -> str:
        raise main.AIProviderNotConfigured("GROQ_API_KEY is missing.")

    monkeypatch.setattr(main, "ask_homer", missing_key)
    response = client.post("/chat", json={"message": "Hello"})

    assert response.status_code == 503
    assert response.json()["detail"] == "GROQ_API_KEY is missing."


def test_chat_hides_provider_internal_errors(monkeypatch) -> None:
    async def provider_error(_message: str) -> str:
        raise RuntimeError("internal exception with secret details")

    monkeypatch.setattr(main, "ask_homer", provider_error)
    response = client.post("/chat", json={"message": "Hello"})

    assert response.status_code == 502
    assert "internal exception with secret details" not in response.text



def test_chat_settings_returns_safe_active_configuration(monkeypatch) -> None:
    class FakeSettings:
        llm_provider = "groq"
        groq_api_key = "a-secret-test-key"
        groq_model = "test-model"
        groq_temperature = 0.4
        groq_top_p = 0.9
        groq_reasoning_effort = "high"
        groq_max_output_tokens = 600
        groq_timeout_seconds = 45.0
        groq_max_retries = 2
        chat_history_messages = 12
        max_message_chars = 2000

    monkeypatch.setattr(main, "get_settings", lambda: FakeSettings())
    response = client.get("/chat/settings")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "groq",
        "model": "test-model",
        "temperature": 0.4,
        "top_p": 0.9,
        "reasoning_effort": "high",
        "max_output_tokens": 600,
        "timeout_seconds": 45.0,
        "max_retries": 2,
        "history_messages": 12,
        "max_message_chars": 2000,
        "api_key_configured": True,
    }
    assert "a-secret-test-key" not in response.text


def test_chat_enforces_configured_message_limit(monkeypatch) -> None:
    class FakeSettings:
        max_message_chars = 8

    monkeypatch.setattr(main, "get_settings", lambda: FakeSettings())

    async def should_not_run(_message: str) -> str:
        raise AssertionError("AI provider should not be called for an oversized message")

    monkeypatch.setattr(main, "ask_homer", should_not_run)
    response = client.post("/chat", json={"message": "123456789"})

    assert response.status_code == 422


def test_knowledge_status_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(main, "knowledge_status", lambda: {
        "documents": 3, "chunks": 12, "document_directory": "local-documents"
    })
    response = client.get("/knowledge/status")
    assert response.status_code == 200
    assert response.json()["documents"] == 3
    assert response.json()["chunks"] == 12


def test_knowledge_search_endpoint(monkeypatch) -> None:
    class FakeResult:
        def as_dict(self):
            return {"title": "guide.md", "source_type": "document", "chunk": "retrieved"}

    def fake_search(query, limit):
        assert query == "RAG"
        assert limit == 2
        return [FakeResult()]

    monkeypatch.setattr(main, "search_knowledge", fake_search)
    response = client.get("/knowledge/search", params={"q": "RAG", "limit": 2})
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["title"] == "guide.md"


def test_knowledge_search_rejects_invalid_limit() -> None:
    response = client.get("/knowledge/search", params={"q": "RAG", "limit": 99})
    assert response.status_code == 422



def test_streamable_http_mcp_endpoint_is_mounted():
    mounted_paths = {
        getattr(route, "path", None)
        for route in main.app.routes
    }
    assert "/mcp" in mounted_paths
    assert main.mcp_http_app is not None


def test_mcp_streamable_http_endpoint_starts_with_app_lifespan():
    with TestClient(main.app) as lifespan_client:
        response = lifespan_client.get("/mcp/")
    assert response.status_code != 404


def test_ai_status_reports_online_first_and_offline_readiness(monkeypatch) -> None:
    class FakeSettings:
        groq_model = "test-model"
        groq_api_key = "test-key"
        offline_fallback_enabled = True

    monkeypatch.setattr(main, "get_settings", lambda: FakeSettings())
    from app.ai import offline_model
    monkeypatch.setattr(offline_model, "model_status", lambda: {
        "ready": True, "size_mb": 429.0
    })
    response = client.get("/ai/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "online_first"
    assert payload["primary_provider"] == "groq"
    assert payload["offline_fallback_enabled"] is True
    assert payload["offline_model_ready"] is True
    assert "test-key" not in response.text
