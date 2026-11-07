"""Unit tests for the local action registry; these tests never launch apps."""

from app.tools import registry


def test_unknown_tool_is_rejected() -> None:
    result = registry.execute_tool("run_powershell", {})
    assert result["ok"] is False
    assert result["error"] == "Tool is not allowed."


def test_notepad_rejects_arguments() -> None:
    result = registry.execute_tool("open_notepad", {"path": "C:/secret.txt"})
    assert result["ok"] is False
    assert result["error"] == "open_notepad accepts no arguments."


def test_notepad_is_windows_only(monkeypatch) -> None:
    monkeypatch.setattr(registry.platform, "system", lambda: "Linux")
    result = registry.execute_tool("open_notepad", {})
    assert result["ok"] is False
    assert result["error"] == "Opening Notepad is only supported on Windows."


def test_notepad_launch_is_called_on_windows(monkeypatch) -> None:
    calls: list[tuple[tuple, dict]] = []

    def fake_popen(*args, **kwargs):
        calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(registry.platform, "system", lambda: "Windows")
    monkeypatch.setattr(registry.subprocess, "Popen", fake_popen)
    result = registry.execute_tool("open_notepad", {})

    assert result["ok"] is True
    assert calls == [((['notepad.exe'],), {"shell": False})]


def test_system_audio_control_dispatches_to_audio_backend(monkeypatch):
    from app.tools import audio_control
    expected = {"ok": True, "volume": 30, "muted": False}
    monkeypatch.setattr(audio_control, "control_system_audio", lambda action, volume: expected)
    assert registry.execute_tool("system_audio_control", {"action": "get"}) == expected


def test_system_audio_control_rejects_unexpected_arguments():
    result = registry.execute_tool(
        "system_audio_control", {"action": "set", "volume": 30, "shell": "whoami"}
    )
    assert result["ok"] is False


def test_window_minimize_and_restore_dispatch(monkeypatch):
    from app.tools import windows_control
    expected = {"ok": True}
    monkeypatch.setattr(windows_control, "minimize_window", lambda title: expected)
    monkeypatch.setattr(windows_control, "restore_window", lambda title: expected)
    assert registry.execute_tool("minimize_window", {"title": "HOMER"}) == expected
    assert registry.execute_tool("restore_window", {"title": "HOMER"}) == expected


def test_browser_registry_rejects_wrong_argument_types():
    result = registry.execute_tool("browser_control", {"action": [], "url": 7})
    assert result["ok"] is False


def test_audio_registry_rejects_wrong_action_type():
    result = registry.execute_tool("system_audio_control", {"action": {"bad": "type"}})
    assert result["ok"] is False


def test_desktop_context_registry_does_not_capture_screen(monkeypatch):
    from app.tools import audio_control, browser_control, windows_control
    monkeypatch.setattr(windows_control, "list_windows", lambda: {"ok": True, "windows": []})
    monkeypatch.setattr(browser_control, "browser_status", lambda: {"ok": True})
    monkeypatch.setattr(audio_control, "get_system_audio", lambda: {"ok": True, "volume": 50})
    result = registry.execute_tool("get_desktop_context", {})
    assert result["ok"] is True
    assert result["screen_capture"] == "not performed"
