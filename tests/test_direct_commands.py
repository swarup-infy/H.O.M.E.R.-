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
