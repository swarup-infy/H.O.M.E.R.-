"""Tests for HOMER's allowlisted desktop actions."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.tools import registry


def test_unknown_tool_is_rejected():
    assert registry.execute_tool("run_powershell", {})["ok"] is False


def test_unknown_site_is_rejected():
    result = registry.execute_tool("open_website", {"site": "example.com"})
    assert result["ok"] is False


def test_extra_arguments_are_rejected():
    result = registry.execute_tool(
        "open_website", {"site": "youtube", "command": "whoami"}
    )
    assert result["ok"] is False


def test_youtube_search_encodes_query_and_uses_default_browser():
    with patch.object(registry, "_navigate_existing_browser", return_value=False), patch.object(registry.webbrowser, "open", return_value=True) as open_browser:
        result = registry.execute_tool(
            "open_website",
            {"site": "youtube", "search_query": "lofi music"},
        )
    assert result["ok"] is True
    assert result["url"] == "https://www.youtube.com/results?search_query=lofi+music"
    open_browser.assert_called_once_with(result["url"], new=0)


def test_spotify_search_encodes_query():
    with patch.object(registry, "_navigate_existing_browser", return_value=False), patch.object(registry.webbrowser, "open", return_value=True) as open_browser:
        result = registry.execute_tool(
            "open_website",
            {"site": "spotify", "search_query": "Arijit Singh"},
        )
    assert result["ok"] is True
    assert result["url"] == "https://open.spotify.com/search/Arijit+Singh"
    open_browser.assert_called_once_with(result["url"], new=0)


def test_browser_choice_is_validated():
    result = registry.execute_tool(
        "open_website", {"site": "chatgpt", "browser": "edge"}
    )
    assert result["ok"] is False


def test_search_not_allowed_for_chatgpt():
    result = registry.execute_tool(
        "open_website", {"site": "chatgpt", "search_query": "hello"}
    )
    assert result["ok"] is False


def test_screen_tools_are_registered_and_validate_arguments():
    assert registry.execute_tool("inspect_screen", {"unexpected": True})["ok"] is False
    assert registry.execute_tool("click_screen_target", {})["ok"] is False
    assert registry.execute_tool("close_named_window", {"application": "powershell"})["ok"] is False


def test_unknown_computer_use_tool_is_rejected():
    assert registry.execute_tool("read_all_files", {})["ok"] is False



def test_play_youtube_video_attempts_player_interaction():
    fake_ytdlp = MagicMock()
    fake_ytdlp.__enter__.return_value.extract_info.return_value = {
        "entries": [{"id": "test-video-id"}]
    }
    fake_module = SimpleNamespace(YoutubeDL=MagicMock(return_value=fake_ytdlp))
    playback = {"ok": True, "method": "vision_coordinate", "target": "Play button"}

    with (
        patch.dict("sys.modules", {"yt_dlp": fake_module}),
        patch.object(registry.platform, "system", return_value="Windows"),
        patch.object(registry.time, "sleep"),
        patch.object(registry, "_navigate_existing_browser", return_value=True),
        patch("app.tools.computer_use.click_screen_target", return_value=playback) as click,
    ):
        result = registry.execute_tool(
            "play_youtube_video", {"query": "Arijit Singh Kesariya"}
        )

    assert result["ok"] is True
    assert result["url"] == "https://www.youtube.com/watch?v=test-video-id&autoplay=1"
    assert result["playback_attempted"] is True
    assert result["playback_action"] == playback
    click.assert_called_once_with("Play")
