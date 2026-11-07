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
            "description": "Close one window matching a named application, such as Brave, Chrome, Edge, Firefox, Spotify, YouTube, or Notepad.",
            "parameters": {
                "type": "object",
                "properties": {"application": {"type": "string", "enum": ["brave", "chrome", "edge", "firefox", "spotify", "youtube", "notepad"]}},
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
    },
    {
        "type": "function",
        "function": {
            "name": "read_screen",
            "description": "Read the current desktop screenshot with the configured vision model. Only call after the user explicitly asks HOMER to read or describe the screen. The screenshot is sent to Groq and is not intentionally saved.",
            "parameters": {"type": "object", "properties": {"question": {"type": "string", "maxLength": 1000}}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "launch_application",
            "description": "Launch a known Windows app or an exact installed Start Menu shortcut by name; arbitrary commands and executable paths are rejected.",
            "parameters": {"type": "object", "properties": {"application": {"type": "string", "minLength": 1, "maxLength": 80}}, "required": ["application"], "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_open_windows",
            "description": "List visible top-level Windows windows and process names; does not read window contents.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "focus_open_window",
            "description": "Focus one uniquely matching visible window by its title.",
            "parameters": {"type": "object", "properties": {"title": {"type": "string", "minLength": 1, "maxLength": 120}}, "required": ["title"], "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_control",
            "description": "Control HOMER's visible dedicated browser. Supports open, navigate, tabs, new_tab, select_tab, close_tab, snapshot, click_text, type_text, press_key, play, pause, toggle, stop, volume, volume_up, volume_down, seek. Navigation is HTTPS and domain-allowlisted. Does not access the user's normal Chrome profile.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["open", "navigate", "back", "forward", "reload", "tabs", "new_tab", "select_tab", "close_tab", "snapshot", "click_text", "type_text", "press_key", "play", "pause", "toggle", "stop", "volume", "volume_up", "volume_down", "seek"]},
                    "url": {"type": "string", "maxLength": 2048},
                    "text": {"type": "string", "maxLength": 2000},
                    "tab_index": {"type": "integer", "minimum": -1, "maximum": 50},
                    "volume": {"type": "integer", "minimum": 0, "maximum": 100},
                    "seconds": {"type": "integer", "minimum": 0, "maximum": 86400},
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_homer_browser",
            "description": "Close only HOMER's dedicated browser window and profile; does not close the user's normal browser.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },

    {
        "type": "function",
        "function": {
            "name": "close_window_by_title",
            "description": "Send a normal close request to exactly one visible Windows window whose title matches the supplied text. Unsaved work may trigger a save prompt.",
            "parameters": {"type": "object", "properties": {"title": {"type": "string", "minLength": 1, "maxLength": 120}}, "required": ["title"], "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "maximize_window",
            "description": "Maximize one uniquely matching visible Windows window by title.",
            "parameters": {"type": "object", "properties": {"title": {"type": "string", "minLength": 1, "maxLength": 120}}, "required": ["title"], "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_workspace_memory",
            "description": "Save a note or project fact to HOMER's local private memory. Only save when the user asks you to remember or save something.",
            "parameters": {"type":"object","properties":{"title":{"type":"string","minLength":1,"maxLength":160},"content":{"type":"string","minLength":1,"maxLength":4000},"category":{"type":"string","maxLength":24}},"required":["title","content"],"additionalProperties":False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_workspace_memory",
            "description": "Search HOMER's local saved notes and project memories.",
            "parameters": {"type":"object","properties":{"query":{"type":"string","minLength":1,"maxLength":200},"limit":{"type":"integer","minimum":1,"maximum":10}},"required":["query"],"additionalProperties":False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_workspace_memory",
            "description": "Delete one saved memory by its ID, only when the user explicitly asks to forget/delete it.",
            "parameters": {"type":"object","properties":{"memory_id":{"type":"integer","minimum":1}},"required":["memory_id"],"additionalProperties":False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": "Create a local one-shot reminder a number of minutes from now. HOMER must be running when it becomes due to display it.",
            "parameters": {"type":"object","properties":{"title":{"type":"string","minLength":1,"maxLength":160},"minutes_from_now":{"type":"integer","minimum":1,"maximum":525600}},"required":["title","minutes_from_now"],"additionalProperties":False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "List reminders saved locally on this device.",
            "parameters": {"type":"object","properties":{"include_completed":{"type":"boolean"}},"additionalProperties":False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_reminder",
            "description": "Mark one local reminder complete by ID.",
            "parameters": {"type":"object","properties":{"reminder_id":{"type":"integer","minimum":1}},"required":["reminder_id"],"additionalProperties":False},
        },
    },
    {
        "type": "function", "function": {
            "name": "start_timer",
            "description": "Start a local countdown up to 24 hours. It does not alter OS settings.",
            "parameters": {"type": "object", "properties": {"seconds":{"type":"integer","minimum":1,"maximum":86400},"label":{"type":"string","maxLength":100}}, "required": ["seconds"], "additionalProperties": False},
        },
    },
    {
        "type": "function", "function": {
            "name": "list_timers",
            "description": "List timers started during the current HOMER process.",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    },
    {
        "type": "function", "function": {
            "name": "get_workspace_presets",
            "description": "List suggested coding, study, creative and focus workspaces; this does not launch apps automatically.",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    },
    {
        "type": "function", "function": {
            "name": "web_search",
            "description": "Open a search query in the default browser using DuckDuckGo or Google.",
            "parameters": {"type": "object", "properties": {"query":{"type":"string","minLength":1,"maxLength":200},"provider":{"type":"string","enum":["duckduckgo","google"]}}, "required": ["query"], "additionalProperties": False},
        },
    },
    {
        "type": "function", "function": {
            "name": "get_weather",
            "description": "Fetch current weather conditions for a city using Open-Meteo.",
            "parameters": {"type": "object", "properties": {"city":{"type":"string","minLength":1,"maxLength":100}}, "required": ["city"], "additionalProperties": False},
        },
    },
    {
        "type": "function", "function": {
            "name": "git_status",
            "description": "Read-only Git status for a project under HOMER or Documents. Does not commit, push or change branches.",
            "parameters": {"type": "object", "properties": {"project_path":{"type":"string","maxLength":500}}, "required": [], "additionalProperties": False},
        },
    },
    {
        "type": "function", "function": {
            "name": "create_code_draft",
            "description": "Prepare a code-generation prompt. Does not write, compile or execute code.",
            "parameters": {"type": "object", "properties": {"description":{"type":"string","minLength":1,"maxLength":2000},"language":{"type":"string","enum":["python","javascript","typescript","html","css","java","c","cpp","rust","go","sql"]}}, "required": ["description"], "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "Read basic local CPU, RAM, disk and battery telemetry. This is read-only.",
            "parameters": {"type":"object","properties":{},"additionalProperties":False},
        },
    },
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
    """Resolve a YouTube result and open it in HOMER's dedicated browser."""
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
        url = "https://www.youtube.com/watch?v=" + first["id"]
        from app.tools.browser_control import browser_action
        opened = browser_action("navigate", url=url)
        if not opened.get("ok"):
            return {"ok": False, "message": "Found the video, but HOMER could not open its browser tab.", "browser_result": opened}
        playback = browser_action("play")
        return {
            "ok": True, "message": "Found and opened the matching YouTube video in HOMER's browser.",
            "url": url, "reused_window": True, "playback_attempted": True,
            "playback_action": playback,
            "note": "A play request is not proof that playback started; check the returned player state.",
        }
    except Exception as exc:
        return {"ok": False, "error": "YouTube search/open failed (" + type(exc).__name__ + "). Install or update yt-dlp if needed."}


def _close_named_window(arguments: dict[str, Any]) -> dict[str, Any]:
    """Ask Windows to close one visible top-level window with a matching title."""
    if set(arguments) != {"application"}:
        return {"ok": False, "error": "Choose an application window to close."}
    app = arguments.get("application")
    if app not in {"brave", "chrome", "edge", "firefox", "spotify", "youtube", "notepad"}:
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

    if name == "save_workspace_memory":
        if set(arguments) - {"title", "content", "category"} or not {"title", "content"} <= set(arguments):
            return {"ok": False, "error": "Provide a title, content, and optional category."}
        from app.memory.workspace import save_memory
        return save_memory(arguments["title"], arguments["content"], arguments.get("category", "note"))
    if name == "search_workspace_memory":
        if set(arguments) - {"query", "limit"} or "query" not in arguments:
            return {"ok": False, "error": "Provide a memory search query."}
        from app.memory.workspace import search_memories
        return search_memories(arguments["query"], arguments.get("limit", 5))
    if name == "delete_workspace_memory":
        if set(arguments) != {"memory_id"}:
            return {"ok": False, "error": "Provide exactly one memory ID."}
        from app.memory.workspace import delete_memory
        return delete_memory(arguments["memory_id"])
    if name == "create_reminder":
        if set(arguments) != {"title", "minutes_from_now"}:
            return {"ok": False, "error": "Provide a reminder title and delay in minutes."}
        from app.tasks.reminders import create_reminder
        return create_reminder(arguments["title"], arguments["minutes_from_now"])
    if name == "list_reminders":
        if set(arguments) - {"include_completed"}:
            return {"ok": False, "error": "Unsupported reminder options."}
        from app.tasks.reminders import list_reminders
        return list_reminders(arguments.get("include_completed", False))
    if name == "complete_reminder":
        if set(arguments) != {"reminder_id"}:
            return {"ok": False, "error": "Provide one reminder ID."}
        from app.tasks.reminders import complete_reminder
        return complete_reminder(arguments["reminder_id"])

    if name in {"start_timer", "list_timers", "get_workspace_presets", "web_search", "get_weather", "git_status", "create_code_draft"}:
        from app.tools import ultron_compat
        handlers = {
            "start_timer": lambda: ultron_compat.start_timer(arguments.get("seconds"), arguments.get("label", "Timer")),
            "list_timers": ultron_compat.list_timers,
            "get_workspace_presets": ultron_compat.workspace_presets,
            "web_search": lambda: ultron_compat.web_search(arguments.get("query", ""), arguments.get("provider", "duckduckgo")),
            "get_weather": lambda: ultron_compat.fetch_weather(arguments.get("city", "")),
            "git_status": lambda: ultron_compat.git_status(arguments.get("project_path", "")),
            "create_code_draft": lambda: ultron_compat.create_code_draft(arguments.get("description", ""), arguments.get("language", "python")),
        }
        required = {
            "start_timer": {"seconds"}, "list_timers": set(), "get_workspace_presets": set(),
            "web_search": {"query"}, "get_weather": {"city"}, "git_status": set(), "create_code_draft": {"description"},
        }
        allowed = {
            "start_timer": {"seconds", "label"}, "list_timers": set(), "get_workspace_presets": set(),
            "web_search": {"query", "provider"}, "get_weather": {"city"}, "git_status": {"project_path"},
            "create_code_draft": {"description", "language"},
        }
        if not required[name] <= set(arguments) or set(arguments) - allowed[name]:
            return {"ok": False, "error": "Invalid arguments for this tool."}
        return handlers[name]()

    if name == "get_system_status":
        if arguments:
            return {"ok": False, "error": "get_system_status accepts no arguments."}
        from app.system.monitor import system_status
        return system_status()

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
    if name == "read_screen":
        if set(arguments) - {"question"}:
            return {"ok": False, "error": "read_screen accepts only an optional question."}
        from app.tools.computer_use import read_screen
        return read_screen(arguments.get("question", "Describe what is visible on my screen."))
    if name == "launch_application":
        if set(arguments) != {"application"}:
            return {"ok": False, "error": "Provide one allowlisted application name."}
        from app.tools.windows_control import launch_application
        return launch_application(arguments["application"])
    if name == "list_open_windows":
        if arguments:
            return {"ok": False, "error": "list_open_windows accepts no arguments."}
        from app.tools.windows_control import list_windows
        return list_windows()
    if name == "maximize_window":
        if set(arguments) != {"title"} or not isinstance(arguments.get("title"), str):
            return {"ok": False, "error": "Provide one window title."}
        from app.tools.windows_control import maximize_window
        return maximize_window(arguments["title"])
    if name == "close_window_by_title":
        if set(arguments) != {"title"} or not isinstance(arguments.get("title"), str):
            return {"ok": False, "error": "Provide one window title."}
        from app.tools.windows_control import close_window_by_title
        return close_window_by_title(arguments["title"])
    if name == "focus_open_window":
        if set(arguments) != {"title"} or not isinstance(arguments.get("title"), str):
            return {"ok": False, "error": "Provide one window title."}
        from app.tools.windows_control import focus_window
        return focus_window(arguments["title"])
    if name == "browser_control":
        if set(arguments) - {"action", "url", "text", "tab_index", "volume", "seconds"} or "action" not in arguments:
            return {"ok": False, "error": "Provide a browser action and only supported optional parameters."}
        from app.tools.browser_control import browser_action
        return browser_action(
            action=arguments["action"],
            url=arguments.get("url", ""),
            text=arguments.get("text", ""),
            tab_index=arguments.get("tab_index", -1),
            volume=arguments.get("volume", 50),
            seconds=arguments.get("seconds", 0),
        )
    if name == "close_homer_browser":
        if arguments:
            return {"ok": False, "error": "close_homer_browser accepts no arguments."}
        from app.tools.browser_control import close_browser
        return close_browser()
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
