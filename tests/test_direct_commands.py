"""Tests for deterministic routing of explicit desktop commands."""
import asyncio
from unittest.mock import patch

from app.ai import groq_client


def test_song_command_routes_directly_to_youtube_tool():
    assert groq_client._direct_desktop_command("Play Harriet song") == (
        "play_youtube_video", {"query": "harriet"}
    )


def test_song_command_handles_song_first_wording():
    assert groq_client._direct_desktop_command("Play the song Kesariya by Arijit Singh") == (
        "play_youtube_video", {"query": "kesariya by arijit singh"}
    )


def test_named_browser_close_does_not_depend_on_llm():
    assert groq_client._direct_desktop_command("Close the Brave window") == (
        "close_named_window", {"application": "brave"}
    )


def test_close_current_window_routes_to_alt_f4_tool():
    assert groq_client._direct_desktop_command("Close the whole window") == (
        "close_active_window", {}
    )


def test_click_command_routes_to_screen_control():
    assert groq_client._direct_desktop_command("Click the Play button") == (
        "click_screen_target", {"target": "play button"}
    )


def test_non_action_question_stays_with_llm():
    assert groq_client._direct_desktop_command("What is machine learning?") is None


def test_direct_command_executes_without_api_key():
    with (
        patch.object(groq_client, "get_settings") as get_settings,
        patch.object(groq_client, "execute_tool", return_value={
            "ok": True,
            "url": "https://www.youtube.com/watch?v=abc&autoplay=1",
            "playback_action": {"ok": True},
        }) as execute,
    ):
        get_settings.return_value.groq_api_key = ""
        reply = asyncio.run(groq_client.ask_homer("Play Harriet song"))
    execute.assert_called_once_with("play_youtube_video", {"query": "harriet"})
    assert "attempted to start playback" in reply


def test_edge_close_command_routes_directly():
    assert groq_client._direct_desktop_command("Close Microsoft Edge") == (
        "close_named_window", {"application": "edge"}
    )


def test_song_by_artist_phrase_removes_generic_song_words():
    assert groq_client._direct_desktop_command("Play a song by Arijit Singh") == (
        "play_youtube_video", {"query": "arijit singh"}
    )



def test_read_screen_routes_to_explicit_vision_tool():
    assert groq_client._direct_desktop_command("Read my screen and tell me what is open") == (
        "read_screen", {"question": "Read my screen and tell me what is open"}
    )


def test_launch_calculator_routes_to_allowlisted_app():
    assert groq_client._direct_desktop_command("Open calculator") == (
        "launch_application", {"application": "calculator"}
    )


def test_browser_volume_up_routes_to_browser_media_control():
    assert groq_client._direct_desktop_command("Turn the browser volume up") == (
        "browser_control", {"action": "volume_up"}
    )


def test_pause_youtube_routes_to_browser_media_control():
    assert groq_client._direct_desktop_command("Pause the YouTube video") == (
        "browser_control", {"action": "pause"}
    )


def test_open_homer_browser_routes_to_browser_service():
    assert groq_client._direct_desktop_command("Open the HOMER browser") == (
        "browser_control", {"action": "open"}
    )


def test_open_youtube_uses_homer_browser():
    assert groq_client._direct_desktop_command("Open YouTube") == (
        "browser_control", {"action": "navigate", "url": "https://www.youtube.com/"}
    )


def test_next_browser_tab_uses_control_tab():
    assert groq_client._direct_desktop_command("Switch to next tab") == (
        "browser_control", {"action": "press_key", "text": "Control+Tab"}
    )


def test_close_window_by_title_routes_directly():
    assert groq_client._direct_desktop_command("Close the window titled Untitled - Notepad") == (
        "close_window_by_title", {"title": "Untitled - Notepad"}
    )



def test_play_generic_video_routes_to_browser_media():
    assert groq_client._direct_desktop_command("Play the video") == (
        "browser_control", {"action": "play"}
    )


def test_stop_video_routes_to_browser_media_stop():
    assert groq_client._direct_desktop_command("Stop the video") == (
        "browser_control", {"action": "stop"}
    )


def test_list_open_windows_routes_directly():
    assert groq_client._direct_desktop_command("Show all open windows") == (
        "list_open_windows", {}
    )


def test_maximize_window_by_title_routes_directly():
    assert groq_client._direct_desktop_command("Maximize window titled HOMER") == (
        "maximize_window", {"title": "HOMER"}
    )
