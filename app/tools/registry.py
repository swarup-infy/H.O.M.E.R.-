"""Allowlisted desktop actions for HOMER.

Actions open known websites only. This module deliberately does not execute
arbitrary shell commands, read browser cookies, or access saved credentials.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
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
        if executable:
            subprocess.Popen([executable, url], shell=False)
        else:
            opened = webbrowser.open(url, new=2)
            if not opened:
                return {"ok": False, "error": "Windows could not open the default browser."}
        return {"ok": True, "message": f"Opened {site.title()}" + (f" search for {query.strip()!r}." if query.strip() else "."), "url": url}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "error": f"Could not open the requested website ({type(exc).__name__})."}


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a permitted action after validating its name and arguments."""
    if not isinstance(arguments, dict):
        return {"ok": False, "error": "Arguments must be an object."}
    if name == "open_website":
        return _open_website(arguments)
    if name != "open_notepad":
        return {"ok": False, "error": "Tool is not allowed."}
    if arguments != {}:
        return {"ok": False, "error": "open_notepad accepts no arguments."}
    if platform.system() != "Windows":
        return {"ok": False, "error": "Opening Notepad is only supported on Windows."}
    try:
        subprocess.Popen(["notepad.exe"], shell=False)
        return {"ok": True, "message": "Notepad launch was requested."}
    except (OSError, subprocess.SubprocessError):
        return {"ok": False, "error": "Windows could not start Notepad."}
