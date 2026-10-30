"""API contract tests; no live Groq request or desktop action is performed."""
from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


def test_health_does_not_expose_api_key(monkeypatch) -> None:
    class FakeSettings:
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
