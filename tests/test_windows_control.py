"""Windows app/window tools are tested without launching real processes."""
from app.tools import windows_control


def test_application_allowlist_rejects_arbitrary_command():
    result = windows_control.launch_application("powershell -enc secret")
    assert result["ok"] is False


def test_application_launch_is_windows_only(monkeypatch):
    monkeypatch.setattr(windows_control.platform, "system", lambda: "Linux")
    result = windows_control.launch_application("calculator")
    assert result["ok"] is False
    assert "Windows only" in result["error"]


def test_window_listing_is_windows_only(monkeypatch):
    monkeypatch.setattr(windows_control.platform, "system", lambda: "Linux")
    assert windows_control.list_windows()["ok"] is False


def test_focus_window_validates_empty_title(monkeypatch):
    monkeypatch.setattr(windows_control.platform, "system", lambda: "Windows")
    result = windows_control.focus_window(" ")
    assert result["ok"] is False


def test_maximize_window_is_windows_only(monkeypatch):
    monkeypatch.setattr(windows_control.platform, "system", lambda: "Linux")
    result = windows_control.maximize_window("HOMER")
    assert result["ok"] is False
    assert "Windows only" in result["error"]


def test_close_window_by_title_rejects_empty_title(monkeypatch):
    monkeypatch.setattr(windows_control.platform, "system", lambda: "Windows")
    result = windows_control.close_window_by_title(" ")
    assert result["ok"] is False


def test_minimize_window_is_windows_only(monkeypatch):
    monkeypatch.setattr(windows_control.platform, "system", lambda: "Linux")
    result = windows_control.minimize_window("HOMER")
    assert result["ok"] is False
    assert "Windows only" in result["error"]


def test_restore_window_is_windows_only(monkeypatch):
    monkeypatch.setattr(windows_control.platform, "system", lambda: "Linux")
    result = windows_control.restore_window("HOMER")
    assert result["ok"] is False
    assert "Windows only" in result["error"]


def test_window_match_rejects_ambiguous_or_empty_title(monkeypatch):
    monkeypatch.setattr(windows_control.platform, "system", lambda: "Windows")
    _, error = windows_control._matching_windows(" ")
    assert error["ok"] is False


def test_installed_app_discovery_validates_limit(monkeypatch):
    monkeypatch.setattr(windows_control.platform, "system", lambda: "Windows")
    assert windows_control.list_installed_applications(0)["ok"] is False
