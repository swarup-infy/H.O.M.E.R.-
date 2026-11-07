"""MCP server registration and registry bridge tests."""
from unittest.mock import patch

from app.mcp_server import mcp
from app.tools import registry


def test_mcp_server_is_registered():
    assert mcp is not None


def test_registry_exposes_mcp_actions():
    names = {item["function"]["name"] for item in registry.TOOL_DEFINITIONS}
    assert {
        "read_screen", "launch_application", "list_open_windows",
        "focus_open_window", "maximize_window", "browser_control", "close_homer_browser",
        "save_workspace_memory", "search_workspace_memory", "create_reminder", "get_system_status",
    }.issubset(names)


def test_browser_control_dispatches_only_supported_arguments():
    expected = {"ok": True, "tabs": []}
    with patch("app.tools.browser_control.browser_action", return_value=expected) as action:
        result = registry.execute_tool("browser_control", {"action": "tabs"})
    assert result == expected
    action.assert_called_once_with(
        action="tabs", url="", text="", tab_index=-1, volume=50, seconds=0
    )


def test_browser_control_rejects_unexpected_arguments():
    result = registry.execute_tool("browser_control", {"action": "tabs", "javascript": "alert(1)"})
    assert result["ok"] is False


def test_read_screen_dispatches_to_explicit_screen_reader():
    expected = {"ok": True, "answer": "I can see a browser."}
    with patch("app.tools.computer_use.read_screen", return_value=expected) as reader:
        result = registry.execute_tool("read_screen", {"question": "What is open?"})
    assert result == expected
    reader.assert_called_once_with("What is open?")



def test_close_window_by_title_dispatches_safely():
    expected = {"ok": True, "window_title": "Untitled - Notepad"}
    with patch("app.tools.windows_control.close_window_by_title", return_value=expected) as close:
        result = registry.execute_tool("close_window_by_title", {"title": "Untitled - Notepad"})
    assert result == expected
    close.assert_called_once_with("Untitled - Notepad")


def test_maximize_window_dispatches_by_title():
    expected = {"ok": True, "window_title": "HOMER"}
    with patch("app.tools.windows_control.maximize_window", return_value=expected) as maximize:
        result = registry.execute_tool("maximize_window", {"title": "HOMER"})
    assert result == expected
    maximize.assert_called_once_with("HOMER")
