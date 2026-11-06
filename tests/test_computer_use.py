"""Unit tests for HOMER's screen-control dispatch without touching the real desktop."""
from unittest.mock import patch

from app.tools import registry


def test_inspect_screen_dispatches_to_computer_use():
    expected = {"ok": True, "active_window": "YouTube", "controls": []}
    with patch("app.tools.computer_use.inspect_screen", return_value=expected):
        assert registry.execute_tool("inspect_screen", {}) == expected


def test_click_screen_target_dispatches_to_computer_use():
    expected = {"ok": True, "method": "windows_ui_automation", "target": "Play"}
    with patch("app.tools.computer_use.click_screen_target", return_value=expected) as click:
        result = registry.execute_tool("click_screen_target", {"target": "Play"})
    assert result == expected
    click.assert_called_once_with("Play")


def test_click_screen_target_rejects_extra_arguments():
    result = registry.execute_tool("click_screen_target", {"target": "Play", "x": 10})
    assert result["ok"] is False


def test_named_window_close_dispatches_to_computer_use():
    expected = {"ok": True, "message": "Sent a close request."}
    with patch("app.tools.computer_use.close_window", return_value=expected) as close:
        result = registry.execute_tool("close_named_window", {"application": "brave"})
    assert result == expected
    close.assert_called_once_with("brave")


def test_named_window_close_rejects_unsupported_application():
    result = registry.execute_tool("close_named_window", {"application": "powershell"})
    assert result["ok"] is False



def test_screen_reading_is_windows_only(monkeypatch):
    from app.tools import computer_use

    monkeypatch.setattr(computer_use.platform, "system", lambda: "Linux")
    result = computer_use.read_screen("What is visible?")
    assert result["ok"] is False
    assert "Windows only" in result["error"]


def test_screen_reading_validates_question_before_capture(monkeypatch):
    from app.tools import computer_use

    monkeypatch.setattr(computer_use.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        computer_use,
        "_capture_screenshot",
        lambda: (_ for _ in ()).throw(AssertionError("must validate before capture")),
    )
    result = computer_use.read_screen(" ")
    assert result["ok"] is False
    assert "1-1,000 characters" in result["error"]
