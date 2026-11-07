"""Allowlisted Windows application and top-level window controls."""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

APPLICATIONS = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "file_explorer": ["explorer.exe"],
    "paint": ["mspaint.exe"],
    "task_manager": ["taskmgr.exe"],
    "terminal": ["wt.exe"],
    "command_prompt": ["cmd.exe"],
    "vscode": ["code"],
    "chrome": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "brave": ["brave.exe"],
    "firefox": ["firefox.exe"],
    "spotify": ["Spotify.exe"],
}


def _known_executable(application: str) -> str | None:
    command = APPLICATIONS[application][0]
    found = shutil.which(command)
    if found:
        return found
    roots = [
        Path(os.environ.get("LOCALAPPDATA", "")),
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")),
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")),
    ]
    candidates = {
        "chrome": [root / "Google/Chrome/Application/chrome.exe" for root in roots],
        "edge": [root / "Microsoft/Edge/Application/msedge.exe" for root in roots],
        "brave": [root / "BraveSoftware/Brave-Browser/Application/brave.exe" for root in roots],
        "firefox": [root / "Mozilla Firefox/firefox.exe" for root in roots],
        "spotify": [root / "Spotify/Spotify.exe" for root in roots],
    }.get(application, [])
    return next((str(path) for path in candidates if path.is_file()), None)


def launch_application(application: str) -> dict[str, Any]:
    """Launch a known app or an exact Start Menu shortcut, never a shell command."""
    if platform.system() != "Windows":
        return {"ok": False, "error": "Application launching is supported on Windows only."}
    if not isinstance(application, str):
        return {"ok": False, "error": "Application must be a name, not a command."}
    name = application.strip().casefold()
    if name in APPLICATIONS:
        executable = _known_executable(name)
        if executable:
            try:
                subprocess.Popen([executable, *APPLICATIONS[name][1:]], shell=False)
                return {"ok": True, "application": name, "message": "Launch request sent to Windows."}
            except (OSError, subprocess.SubprocessError) as exc:
                return {"ok": False, "error": "Could not launch application (" + type(exc).__name__ + ")."}
    if not re.fullmatch(r"[a-zA-Z0-9 _.-]{1,80}", name):
        return {"ok": False, "error": "Application name contains unsupported characters."}
    appdata = Path(os.environ.get("APPDATA", ""))
    program_data = Path(os.environ.get("PROGRAMDATA", ""))
    roots = [
        appdata / "Microsoft/Windows/Start Menu/Programs",
        program_data / "Microsoft/Windows/Start Menu/Programs",
    ]
    shortcuts = [
        item for root in roots if root.is_dir()
        for item in root.rglob("*.lnk")
        if item.stem.casefold() == name.replace("_", " ")
    ]
    if len(shortcuts) != 1:
        return {
            "ok": False,
            "error": "No unique installed Start Menu shortcut matched this application name.",
            "matches": [item.stem for item in shortcuts[:6]],
        }
    try:
        os.startfile(str(shortcuts[0]))
        return {"ok": True, "application": name, "message": "Started the matching Start Menu application shortcut."}
    except OSError as exc:
        return {"ok": False, "error": "Could not launch the application shortcut (" + type(exc).__name__ + ")."}


def list_windows() -> dict[str, Any]:
    """List visible top-level windows without collecting window contents."""
    if platform.system() != "Windows":
        return {"ok": False, "error": "Window enumeration is supported on Windows only."}
    try:
        from pywinauto import Desktop
        import psutil
        rows = []
        for window in Desktop(backend="uia").windows(visible_only=True):
            try:
                title = (window.window_text() or "").strip()
                if not title:
                    continue
                pid = window.process_id()
                try:
                    process = psutil.Process(pid).name()
                except (psutil.Error, OSError):
                    process = "unknown"
                rows.append({"title": title[:160], "process": process[:80], "pid": pid})
                if len(rows) >= 60:
                    break
            except Exception:
                continue
        return {"ok": True, "windows": rows}
    except Exception as exc:
        return {"ok": False, "error": "Could not list windows (" + type(exc).__name__ + ")."}


def focus_window(title: str) -> dict[str, Any]:
    """Focus a uniquely matching visible window title."""
    if platform.system() != "Windows":
        return {"ok": False, "error": "Window focus is supported on Windows only."}
    target = title.strip().casefold()
    if not target or len(target) > 120:
        return {"ok": False, "error": "Provide a window title of 1-120 characters."}
    try:
        from pywinauto import Desktop
        matches = []
        for window in Desktop(backend="uia").windows(visible_only=True):
            try:
                name = (window.window_text() or "").strip()
                if target in name.casefold():
                    matches.append((window, name))
            except Exception:
                continue
        if len(matches) != 1:
            return {"ok": False, "error": f"Expected one matching window, found {len(matches)}.",
                    "matches": [name[:120] for _, name in matches[:8]]}
        window, name = matches[0]
        window.restore()
        window.set_focus()
        return {"ok": True, "focused": name}
    except Exception as exc:
        return {"ok": False, "error": "Could not focus window (" + type(exc).__name__ + ")."}


def close_window_by_title(title: str) -> dict[str, Any]:
    """Send WM_CLOSE to exactly one visible top-level window matching its title."""
    if platform.system() != "Windows":
        return {"ok": False, "error": "Window closing is supported on Windows only."}
    target = title.strip().casefold()
    if not target or len(target) > 120:
        return {"ok": False, "error": "Provide a window title of 1-120 characters."}
    try:
        from pywinauto import Desktop
        matches = []
        for window in Desktop(backend="uia").windows(visible_only=True):
            try:
                name = (window.window_text() or "").strip()
                if name and target in name.casefold():
                    matches.append((window, name))
            except Exception:
                continue
        if len(matches) != 1:
            return {
                "ok": False,
                "error": f"Expected one matching window, found {len(matches)}.",
                "matches": [name[:120] for _, name in matches[:8]],
            }
        window, name = matches[0]
        window.close()
        try:
            still_visible = bool(window.is_visible())
        except Exception:
            try:
                still_visible = bool(window.exists(timeout=0.5))
            except Exception:
                still_visible = False
        return {
            "ok": not still_visible,
            "window_title": name,
            "close_requested": True,
            "still_visible_after_request": still_visible,
            "message": (
                "Sent a normal close request, but the window remains visible. "
                "It may be showing an unsaved-work confirmation."
                if still_visible else
                "The requested window is no longer visible."
            ),
        }
    except Exception as exc:
        return {"ok": False, "error": "Could not close the requested window (" + type(exc).__name__ + ")."}


def maximize_window(title: str) -> dict[str, Any]:
    """Maximize exactly one visible top-level window matching its title."""
    if platform.system() != "Windows":
        return {"ok": False, "error": "Window maximizing is supported on Windows only."}
    target = title.strip().casefold()
    if not target or len(target) > 120:
        return {"ok": False, "error": "Provide a window title of 1-120 characters."}
    try:
        from pywinauto import Desktop
        matches = []
        for window in Desktop(backend="uia").windows(visible_only=True):
            try:
                name = (window.window_text() or "").strip()
                if name and target in name.casefold():
                    matches.append((window, name))
            except Exception:
                continue
        if len(matches) != 1:
            return {
                "ok": False,
                "error": f"Expected one matching window, found {len(matches)}.",
                "matches": [name[:120] for _, name in matches[:8]],
            }
        window, name = matches[0]
        window.restore()
        window.maximize()
        return {"ok": True, "window_title": name, "message": "Maximized the requested window."}
    except Exception as exc:
        return {"ok": False, "error": "Could not maximize the requested window (" + type(exc).__name__ + ")."}


def _matching_windows(title: str):
    """Return visible windows whose title contains a validated search string."""
    if platform.system() != "Windows":
        return None, {"ok": False, "error": "Window controls are supported on Windows only."}
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 120:
        return None, {"ok": False, "error": "Provide a window title of 1-120 characters."}
    try:
        from pywinauto import Desktop
        target = title.strip().casefold()
        matches = []
        for window in Desktop(backend="uia").windows(visible_only=True):
            try:
                name = (window.window_text() or "").strip()
                if name and target in name.casefold():
                    matches.append((window, name))
            except Exception:
                continue
        if len(matches) != 1:
            return None, {
                "ok": False,
                "error": f"Expected one matching window, found {len(matches)}.",
                "matches": [name[:120] for _, name in matches[:8]],
            }
        return matches[0], None
    except Exception as exc:
        return None, {"ok": False, "error": "Window lookup failed (" + type(exc).__name__ + ")."}


def minimize_window(title: str) -> dict[str, Any]:
    """Minimize exactly one visible top-level window by its title."""
    match, error = _matching_windows(title)
    if error:
        return error
    window, name = match
    try:
        window.minimize()
        return {"ok": True, "window_title": name, "message": "Minimized the requested window."}
    except Exception as exc:
        return {"ok": False, "error": "Could not minimize the requested window (" + type(exc).__name__ + ")."}


def restore_window(title: str) -> dict[str, Any]:
    """Restore and focus exactly one visible top-level window by its title."""
    match, error = _matching_windows(title)
    if error:
        return error
    window, name = match
    try:
        window.restore()
        window.set_focus()
        return {"ok": True, "window_title": name, "message": "Restored and focused the requested window."}
    except Exception as exc:
        return {"ok": False, "error": "Could not restore the requested window (" + type(exc).__name__ + ")."}


def list_installed_applications(limit: int = 100) -> dict[str, Any]:
    """List known launchable apps and Start Menu shortcuts without launching them."""
    if platform.system() != "Windows":
        return {"ok": False, "error": "Installed-app discovery is supported on Windows only."}
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        return {"ok": False, "error": "limit must be between 1 and 200."}
    known = sorted(APPLICATIONS)
    roots = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    shortcuts = set()
    for root in roots:
        if root.is_dir():
            try:
                for item in root.rglob("*.lnk"):
                    shortcuts.add(item.stem)
                    if len(shortcuts) >= limit:
                        break
            except OSError:
                continue
    names = sorted(set(known).union(shortcuts), key=str.casefold)[:limit]
    return {
        "ok": True,
        "count": len(names),
        "applications": names,
        "hint": "Say 'open <exact application name>' to launch a listed app.",
    }
