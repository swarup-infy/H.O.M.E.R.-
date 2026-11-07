"""MCP server registration and registry bridge tests."""
import asyncio
from unittest.mock import patch

from mcp import Client

from app.mcp_server import mcp
from app.tools import registry


def test_mcp_server_is_registered():
    assert mcp is not None


def test_registry_exposes_mcp_actions():
    names = {item["function"]["name"] for item in registry.TOOL_DEFINITIONS}
    assert {
        "read_screen", "launch_application", "list_open_windows",
        "focus_open_window", "maximize_window", "browser_control", "close_homer_browser",
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


def test_mcp_in_process_client_sees_desktop_and_media_tools():
    async def inspect_tools():
        async with Client(mcp, raise_exceptions=True) as client:
            result = await client.list_tools()
            return {tool.name for tool in result.tools}

    names = asyncio.run(inspect_tools())
    assert {
        "inspect_screen", "read_screen", "click_visible_control",
        "list_open_windows", "list_installed_applications",
        "focus_open_window", "minimize_window_by_title",
        "restore_window_by_title", "maximize_window_by_title",
        "close_window_by_title", "launch_application_by_name",
        "control_active_window", "control_system_audio", "control_media",
        "browser_control", "get_browser_status", "close_homer_browser",
        "search_local_knowledge", "get_desktop_context",
    }.issubset(names)


def test_mcp_control_system_audio_calls_local_audio_backend(monkeypatch):
    expected = {"ok": True, "volume": 35, "muted": False, "device": "default_output"}
    from app.tools import audio_control
    monkeypatch.setattr(audio_control, "control_system_audio", lambda action, volume: expected)

    async def call_tool():
        async with Client(mcp, raise_exceptions=True) as client:
            return await client.call_tool("control_system_audio", {"action": "get"})

    result = asyncio.run(call_tool())
    assert result.is_error is not True
    assert "35" in result.content[0].text


def test_mcp_capabilities_resource_is_registered():
    async def inspect_resources():
        async with Client(mcp, raise_exceptions=True) as client:
            result = await client.list_resources()
            return {str(item.uri) for item in result.resources}

    assert {"homer://capabilities", "homer://desktop/status"}.issubset(
        asyncio.run(inspect_resources())
    )


def test_mcp_voice_prompt_is_registered():
    async def inspect_prompts():
        async with Client(mcp, raise_exceptions=True) as client:
            result = await client.list_prompts()
            return {item.name for item in result.prompts}

    assert "desktop_voice_assistant_guide" in asyncio.run(inspect_prompts())
