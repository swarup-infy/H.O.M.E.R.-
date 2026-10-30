"""Allowlisted desktop actions for HOMER.

Actions open known websites only. This module deliberately does not execute
arbitrary shell commands, read browser cookies, or access saved credentials.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import time
import webbrowser
from typing import Any
from urllib.parse import quote_plus

# Sites are intentionally restricted to this fixed list.
SITES = {
    "youtube": "https://www.youtube.com/",
    "spotify": "https://open.spotify.com/",
    "chatgpt": "https://chatgpt.com/",
    "google": "https://www.google.com/",
    "brave": "https://search.brave.com/",
}

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "open_notepad",
            "description": "Open Windows Notepad. This action does not read or modify files.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": (
                "Open a supported website in the user's existing default browser, "
                "or in Chrome/Brave if requested. Optionally search YouTube, Spotify, "
                "or Google for a user-provided query. Does not sign in or submit forms."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "site": {
                        "type": "string",
                        "enum": ["youtube", "spotify", "chatgpt", "google", "brave"],
                        "description": "Website to open.",
                    },
                    "search_query": {
                        "type": "string",
                        "maxLength": 200,
                        "description": "Optional search terms for YouTube, Spotify, or Google.",
                    },
                    "browser": {
                        "type": "string",
                        "enum": ["default", "chrome", "brave"],
                        "description": "Browser to use; defaults to the Windows default browser.",
                    },
                },
                "required": ["site"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_youtube_video",
            "description": "Find the first matching YouTube video and open its watch page. Use when the user asks to play a named song or video on YouTube.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 200}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_named_window",
            "description": "Close one window matching a named application, such as Brave, Chrome, Spotify, YouTube, or Notepad.",
            "parameters": {
                "type": "object",
                "properties": {"application": {"type": "string", "enum": ["brave", "chrome", "spotify", "youtube", "notepad"]}},
                "required": ["application"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_screen",
            "description": "Inspect the current Windows screen and return the active window and accessible UI control names. Use when the user asks what is visible or before interacting with a visible control.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_screen_target",
            "description": "Click one visible screen control by its human-readable name, for example Play, Pause, Search, or a specific video title. Uses Windows UI Automation first and vision-grounded coordinates as fallback. Only use when the user explicitly asks to click or interact with that target.",
            "parameters": {
                "type": "object",
                "properties": {"target": {"type": "string", "minLength": 1, "maxLength": 160}},
                "required": ["target"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_active_window",
            "description": "Close the currently focused window using Alt+F4. Use only when the user explicitly asks to close the current window. Unsaved work may trigger an application confirmation.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "minimize_active_window",
            "description": "Minimize the currently focused window.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "media_play_pause",
            "description": "Toggle Windows' global media play/pause key for the active media session, such as Spotify or a browser video.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "media_next_track",
            "description": "Skip to the next item in the active Windows media session.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "media_previous_track",
            "description": "Go to the previous item in the active Windows media session.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "seek_youtube_to_time",
            "description": "Seek the currently focused YouTube video to a specific timestamp in seconds by updating the current YouTube URL. Only use when the user explicitly gives a timestamp, for example 6 minutes = 360 seconds.",
            "parameters": {
                "type": "object",
                "properties": {"seconds": {"type": "integer", "minimum": 0, "maximum": 86400}},
                "required": ["seconds"],
                "additionalProperties": False,
            },
        },
    }
]


def _browser_executable(browser: str) -> str | None:
    """Find a requested installed browser without changing its user profile."""
    if browser == "default":
        return None
    if platform.system() != "Windows":
        return shutil.which("chrome" if browser == "chrome" else "brave-browser")
    names = (
        ["chrome.exe", "chrome"]
        if browser == "chrome"
        else ["brave.exe", "brave"]
    )
    found = next((shutil.which(name) for name in names if shutil.which(name)), None)
    if found:
        return found
    import os
    from pathlib import Path

    local = Path(os.environ.get("LOCALAPPDATA", ""))
    program_files = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
    program_files_x86 = Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
    candidates = (
        [
            local / "Google/Chrome/Application/chrome.exe",
            program_files / "Google/Chrome/Application/chrome.exe",
            program_files_x86 / "Google/Chrome/Application/chrome.exe",
        ]
        if browser == "chrome"
        else [
            local / "BraveSoftware/Brave-Browser/Application/brave.exe",
            program_files / "BraveSoftware/Brave-Browser/Application/brave.exe",
            program_files_x86 / "BraveSoftware/Brave-Browser/Application/brave.exe",
        ]
    )
    return next((str(path) for path in candidates if path.is_file()), None)



def _navigate_existing_browser(url: str, browser: str = "default") -> bool:
    """Navigate the current tab of an already-open browser instead of launching another window."""
    if platform.system() != "Windows":
        return False
    try:
        from pywinauto import Desktop
        import pyautogui
        import psutil

        allowed = {"chrome": {"chrome.exe"}, "brave": {"brave.exe"},
                   "default": {"chrome.exe", "brave.exe", "msedge.exe", "firefox.exe"}}
        windows = Desktop(backend="uia").windows(visible_only=True)
        active = None
        try:
            active = Desktop(backend="uia").get_active()
        except Exception:
            pass
        candidates = ([active] if active is not None else []) + [w for w in windows if w != active]
        for window in candidates:
            if window is None:
                continue
            try:
                pid = window.process_id()
                exe = psutil.Process(pid).name().lower()
                if exe not in allowed.get(browser, allowed["default"]):
                    continue
                window.restore()
                window.set_focus()
                time.sleep(0.25)
                pyautogui.hotkey("ctrl", "l")
                pyautogui.write(url, interval=0.001)
                pyautogui.press("enter")
                return True
            except Exception:
                continue
    except Exception:
        return False
    return False

def _open_website(arguments: dict[str, Any]) -> dict[str, Any]:
    allowed = {"site", "search_query", "browser"}
    if set(arguments) - allowed:
        return {"ok": False, "error": "Unexpected arguments."}
    site = arguments.get("site")
    browser = arguments.get("browser", "default")
    query = arguments.get("search_query", "")
    if site not in SITES:
        return {"ok": False, "error": "That website is not on HOMER's allowlist."}
    if browser not in {"default", "chrome", "brave"}:
        return {"ok": False, "error": "Unsupported browser choice."}
    if not isinstance(query, str) or len(query) > 200:
        return {"ok": False, "error": "Search query must be text of at most 200 characters."}
    if query and site not in {"youtube", "spotify", "google"}:
        return {"ok": False, "error": "Search is supported only for YouTube, Spotify, and Google."}

    url = SITES[site]
    if query:
        encoded = quote_plus(query.strip())
        if site == "youtube":
            url = f"https://www.youtube.com/results?search_query={encoded}"
        elif site == "spotify":
            url = f"https://open.spotify.com/search/{encoded}"
        else:
            url = f"https://www.google.com/search?q={encoded}"

    try:
        executable = _browser_executable(browser)
        if browser != "default" and executable is None:
            return {"ok": False, "error": f"Could not find the installed {browser.title()} browser."}
        if _navigate_existing_browser(url, browser):
            return {"ok": True, "message": f"Navigated the existing browser tab to {site.title()}" + (f" search for {query.strip()!r}." if query.strip() else "."), "url": url, "reused_window": True}
        if executable:
            subprocess.Popen([executable, url], shell=False)
        else:
            opened = webbrowser.open(url, new=0)
            if not opened:
                return {"ok": False, "error": "Windows could not open the default browser."}
        return {"ok": True, "message": f"Opened {site.title()}" + (f" search for {query.strip()!r}." if query.strip() else "."), "url": url, "reused_window": False}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "error": f"Could not open the requested website ({type(exc).__name__})."}



def _play_youtube_video(arguments: dict[str, Any]) -> dict[str, Any]:
    """Resolve the first YouTube search result to a direct watch URL."""
    if set(arguments) != {"query"}:
        return {"ok": False, "error": "Provide only a video or song query."}
    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip() or len(query) > 200:
        return {"ok": False, "error": "Query must be 1-200 characters."}
    try:
        import yt_dlp
        options = {"quiet": True, "no_warnings": True, "skip_download": True,
                   "extract_flat": True, "default_search": "ytsearch1"}
        with yt_dlp.YoutubeDL(options) as ydl:
            result = ydl.extract_info("ytsearch1:" + query.strip(), download=False)
        entries = result.get("entries") if isinstance(result, dict) else None
        first = next((item for item in (entries or []) if item), None)
        if not first or not first.get("id"):
            return {"ok": False, "error": "No matching YouTube video was found."}
        # Request autoplay, then explicitly try to activate the visible player control.
        # Browser autoplay policies vary, so the click result is reported separately.
        url = "https://www.youtube.com/watch?v=" + first["id"] + "&autoplay=1"
        reused = _navigate_existing_browser(url, "default")
        if not reused:
            opened = webbrowser.open(url, new=0)
            if not opened:
                return {"ok": False, "error": "Windows could not open the YouTube video."}
        playback = {"ok": False, "error": "Playback click was not attempted on this platform."}
        if platform.system() == "Windows":
            time.sleep(2.5)
            try:
                from app.tools.computer_use import click_screen_target
                playback = click_screen_target("Play button on the YouTube video player")
            except Exception as exc:
                playback = {"ok": False, "error": "Playback interaction failed (" + type(exc).__name__ + ")."}
        return {
            "ok": True,
            "message": "Found and opened the matching YouTube video.",
            "url": url,
            "reused_window": reused,
            "playback_attempted": platform.system() == "Windows",
            "playback_action": playback,
            "note": "A successful click is not proof that audio is playing; check the player state."
        }
    except Exception as exc:
        return {"ok": False, "error": "YouTube search/open failed (" + type(exc).__name__ + "). Install or update yt-dlp if needed."}


def _close_named_window(arguments: dict[str, Any]) -> dict[str, Any]:
    """Ask Windows to close one visible top-level window with a matching title."""
    if set(arguments) != {"application"}:
        return {"ok": False, "error": "Choose an application window to close."}
    app = arguments.get("application")
    if app not in {"brave", "chrome", "spotify", "youtube", "notepad"}:
        return {"ok": False, "error": "Unsupported application name."}
    if platform.system() != "Windows":
        return {"ok": False, "error": "Named window controls are supported on Windows only."}
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    matches: list[int] = []
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd: int, _param: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            title = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title, length + 1)
            title_matches = app in title.value.lower()
            process_matches = False
            if app in {"brave", "chrome"}:
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                process = kernel32.OpenProcess(0x1000, False, pid.value)
                if process:
                    try:
                        image = ctypes.create_unicode_buffer(1024)
                        size = wintypes.DWORD(len(image))
                        if kernel32.QueryFullProcessImageNameW(process, 0, image, ctypes.byref(size)):
                            exe = image.value.replace("/", "\\").rsplit("\\", 1)[-1].lower()
                            process_matches = exe == ("brave.exe" if app == "brave" else "chrome.exe")
                    finally:
                        kernel32.CloseHandle(process)
            if process_matches or (app not in {"brave", "chrome"} and title_matches):
                matches.append(int(hwnd))
        return True
    user32.EnumWindows(enum_proc(callback), 0)
    if not matches:
        return {"ok": False, "error": "No visible window title matched " + app.title() + "."}
    user32.PostMessageW(matches[0], 0x0010, 0, 0)
    return {"ok": True, "message": "Sent a close request to one " + app.title() + " window. Unsaved work may require confirmation."}


def _press_media_key(virtual_key: int) -> dict[str, Any]:
    """Send a Windows media key without depending on third-party packages."""
    if platform.system() != "Windows":
        return {"ok": False, "error": "Media-key control is currently supported on Windows only."}
    try:
        import ctypes
        KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(virtual_key, 0, 0, 0)
        ctypes.windll.user32.keybd_event(virtual_key, 0, KEYEVENTF_KEYUP, 0)
        return {"ok": True, "message": "Media key sent."}
    except Exception as exc:
        return {"ok": False, "error": f"Could not send media key ({type(exc).__name__})."}


def _desktop_action(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Run a narrowly scoped desktop action."""
    no_args = {"close_active_window", "minimize_active_window", "media_play_pause",
               "media_next_track", "media_previous_track"}
    if name in no_args and arguments:
        return {"ok": False, "error": f"{name} accepts no arguments."}
    if name == "open_notepad":
        if arguments:
            return {"ok": False, "error": "open_notepad accepts no arguments."}
        if platform.system() != "Windows":
            return {"ok": False, "error": "Opening Notepad is only supported on Windows."}
        try:
            subprocess.Popen(["notepad.exe"], shell=False)
            return {"ok": True, "message": "Notepad launch was requested."}
        except (OSError, subprocess.SubprocessError):
            return {"ok": False, "error": "Windows could not start Notepad."}
    if name in {"close_active_window", "minimize_active_window"}:
        if platform.system() != "Windows":
            return {"ok": False, "error": "Window controls are currently supported on Windows only."}
        try:
            import pyautogui
            if name == "close_active_window":
                pyautogui.hotkey("alt", "f4")
                return {"ok": True, "message": "Sent Alt+F4 to the focused window. Check for any unsaved-work prompt."}
            pyautogui.hotkey("win", "down")
            return {"ok": True, "message": "Asked Windows to minimize the focused window."}
        except Exception as exc:
            return {"ok": False, "error": f"Window control failed ({type(exc).__name__})."}
    media_keys = {"media_play_pause": 0xB3, "media_next_track": 0xB0, "media_previous_track": 0xB1}
    if name in media_keys:
        return _press_media_key(media_keys[name])
    if name == "seek_youtube_to_time":
        if set(arguments) != {"seconds"}:
            return {"ok": False, "error": "Provide only a seconds timestamp."}
        seconds = arguments.get("seconds")
        if not isinstance(seconds, int) or isinstance(seconds, bool) or not 0 <= seconds <= 86400:
            return {"ok": False, "error": "Timestamp must be an integer from 0 to 86400 seconds."}
        if platform.system() != "Windows":
            return {"ok": False, "error": "YouTube timestamp control is currently supported on Windows only."}
        try:
            import pyautogui
            import tkinter as tk
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            pyautogui.hotkey("ctrl", "l")
            pyautogui.hotkey("ctrl", "c")
            root = tk.Tk()
            root.withdraw()
            root.update()
            current_url = root.clipboard_get().strip()
            parsed = urlparse(current_url)
            if parsed.hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtube-nocookie.com"}:
                root.destroy()
                return {"ok": False, "error": "Focus the browser tab with the YouTube video first."}
            params = parse_qs(parsed.query)
            params["t"] = [str(seconds) + "s"]
            updated = urlunparse(parsed._replace(query=urlencode(params, doseq=True)))
            root.clipboard_clear()
            root.clipboard_append(updated)
            root.update()
            root.destroy()
            pyautogui.hotkey("ctrl", "v")
            pyautogui.press("enter")
            return {"ok": True, "message": f"Asked the focused YouTube tab to seek to {seconds // 60}:{seconds % 60:02d}. The video may reload."}
        except Exception as exc:
            return {"ok": False, "error": f"YouTube seeking failed ({type(exc).__name__}). Focus the video's browser tab and try again."}
    return {"ok": False, "error": "Tool is not allowed."}


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a permitted action after validating its name and arguments."""
    if not isinstance(arguments, dict):
        return {"ok": False, "error": "Arguments must be an object."}
    if name == "open_website":
        return _open_website(arguments)
    if name == "play_youtube_video":
        return _play_youtube_video(arguments)
    if name == "close_named_window":
        if set(arguments) != {"application"}:
            return {"ok": False, "error": "Choose the application window to close."}
        from app.tools.computer_use import close_window
        return close_window(arguments["application"])
    if name == "inspect_screen":
        if arguments:
            return {"ok": False, "error": "inspect_screen accepts no arguments."}
        from app.tools.computer_use import inspect_screen
        return inspect_screen()
    if name == "click_screen_target":
        if set(arguments) != {"target"} or not isinstance(arguments.get("target"), str):
            return {"ok": False, "error": "Provide one target description."}
        from app.tools.computer_use import click_screen_target
        return click_screen_target(arguments["target"])
    allowed = {"open_notepad", "close_active_window", "minimize_active_window",
               "media_play_pause", "media_next_track", "media_previous_track",
               "seek_youtube_to_time"}
    if name not in allowed:
        return {"ok": False, "error": "Tool is not allowed."}
    return _desktop_action(name, arguments)
