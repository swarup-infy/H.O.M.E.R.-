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
