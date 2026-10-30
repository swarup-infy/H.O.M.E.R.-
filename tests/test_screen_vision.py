"""Tests for opt-in screen analysis endpoint."""
import base64

from fastapi.testclient import TestClient

from app.main import app
from app.ai import vision_client

client = TestClient(app)


def test_screen_ask_rejects_non_jpeg_data_url():
    response = client.post(
        "/screen/ask",
        json={"prompt": "What is this?", "image_data_url": "data:image/png;base64,YWJj"},
    )
    assert response.status_code == 422


def test_screen_ask_rejects_invalid_base64():
    response = client.post(
        "/screen/ask",
        json={"prompt": "What is this?", "image_data_url": "data:image/jpeg;base64,%%%"},
    )
    assert response.status_code == 422


def test_screen_ask_calls_vision_client(monkeypatch):
    async def fake_ask(prompt, image_data_url):
        assert prompt == "Explain this screen"
        assert image_data_url == "data:image/jpeg;base64," + base64.b64encode(b"jpeg").decode()
        return "I can see a desktop."

    monkeypatch.setattr(vision_client, "ask_about_image", fake_ask)
    response = client.post(
        "/screen/ask",
        json={
            "prompt": "Explain this screen",
            "image_data_url": "data:image/jpeg;base64," + base64.b64encode(b"jpeg").decode(),
        },
    )
    assert response.status_code == 200
    assert response.json()["reply"] == "I can see a desktop."


def test_screen_ask_hides_provider_errors(monkeypatch):
    async def fail_ask(prompt, image_data_url):
        raise RuntimeError("private provider detail")

    monkeypatch.setattr(vision_client, "ask_about_image", fail_ask)
    response = client.post(
        "/screen/ask",
        json={
            "prompt": "Explain this screen",
            "image_data_url": "data:image/jpeg;base64," + base64.b64encode(b"jpeg").decode(),
        },
    )
    assert response.status_code == 502
    assert "private provider detail" not in response.text
