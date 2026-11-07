
"""HOMER-native, permission-bounded utilities inspired by Ultron's useful workflows.

These functions intentionally avoid Ultron's self-modifying code, arbitrary
shell execution, biometric/sentry collection, destructive cleanup, and
unrestricted background surveillance.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from app.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAX_DOCUMENT_BYTES = 2_000_000
ALLOWED_TEXT_SUFFIXES = {".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".yaml", ".yml", ".toml", ".log", ".ini"}
ALLOWED_URL_HOSTS = {"github.com", "www.github.com", "arxiv.org", "www.arxiv.org", "scholar.google.com", "www.google.com", "www.youtube.com"}

_timer_lock = threading.Lock()
_timers: dict[str, dict[str, Any]] = {}


def _clean_text(value: str, limit: int = 4000) -> str:
    return str(value or "").strip()[:limit]


def read_project_file(path: str, max_bytes: int = MAX_DOCUMENT_BYTES) -> dict[str, Any]:
    """Read a text file only inside the HOMER project or user's Documents folder."""
    if not isinstance(path, str) or not path.strip():
        return {"ok": False, "error": "A file path is required."}
    candidate = Path(path).expanduser()
    allowed_roots = [PROJECT_ROOT.resolve(), (Path.home() / "Documents").resolve()]
    try:
        resolved = candidate.resolve(strict=True)
        if not any(resolved == root or root in resolved.parents for root in allowed_roots):
            return {"ok": False, "error": "File is outside HOMER's allowed project/Documents folders."}
        if not resolved.is_file() or resolved.suffix.lower() not in ALLOWED_TEXT_SUFFIXES:
            return {"ok": False, "error": "Only supported text files can be read."}
        if resolved.stat().st_size > max_bytes:
            return {"ok": False, "error": f"File exceeds the {max_bytes} byte limit."}
        return {"ok": True, "path": str(resolved), "content": resolved.read_text(encoding="utf-8", errors="replace")}
    except (OSError, RuntimeError) as exc:
        return {"ok": False, "error": f"Could not read file: {exc}"}


def start_timer(seconds: int, label: str = "Timer") -> dict[str, Any]:
    """Start a bounded local countdown. It only logs completion; it does not control OS settings."""
    if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= 86400:
        return {"ok": False, "error": "Timer duration must be from 1 to 86400 seconds."}
    timer_id = f"homer-{time.time_ns()}"
    item = {"id": timer_id, "label": _clean_text(label, 100) or "Timer", "seconds": seconds, "status": "running"}
    with _timer_lock:
        _timers[timer_id] = item

    def finish() -> None:
        time.sleep(seconds)
        with _timer_lock:
            current = _timers.get(timer_id)
            if current and current["status"] == "running":
                current["status"] = "completed"

    threading.Thread(target=finish, name="HOMER-timer", daemon=True).start()
    return {"ok": True, **item}


def list_timers() -> dict[str, Any]:
    with _timer_lock:
        return {"ok": True, "timers": [dict(v) for v in _timers.values()]}


def workspace_presets() -> dict[str, Any]:
    """Return non-executing workspace presets; no apps are launched automatically."""
    return {
        "ok": True,
        "presets": {
            "coding": {"apps": ["Visual Studio Code"], "urls": ["https://github.com"], "description": "Development workspace"},
            "study": {"apps": [], "urls": ["https://scholar.google.com", "https://arxiv.org"], "description": "Research workspace"},
            "creative": {"apps": [], "urls": ["https://www.youtube.com"], "description": "Creative workspace"},
            "focus": {"apps": [], "urls": [], "description": "Quiet focus workspace"},
        },
        "note": "Presets are suggestions only; HOMER never launches multiple apps or changes system settings automatically.",
    }


def web_search(query: str, provider: str = "duckduckgo") -> dict[str, Any]:
    """Open an allowlisted search provider page; it does not scrape or submit forms."""
    q = _clean_text(query, 200)
    if not q:
        return {"ok": False, "error": "Search query is required."}
    if provider == "duckduckgo":
        url = "https://duckduckgo.com/?q=" + quote_plus(q)
    elif provider == "google":
        url = "https://www.google.com/search?q=" + quote_plus(q)
    else:
        return {"ok": False, "error": "Unsupported search provider."}
    try:
        import webbrowser
        opened = webbrowser.open(url)
        return {"ok": bool(opened), "url": url, "query": q, "message": "Opened search in your browser." if opened else "Browser did not open."}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def fetch_weather(city: str) -> dict[str, Any]:
    """Fetch simple current conditions from Open-Meteo geocoding and forecast endpoints."""
    name = _clean_text(city, 100)
    if not name:
        return {"ok": False, "error": "City is required."}
    try:
        from urllib.parse import urlencode
        geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urlencode({"name": name, "count": 1, "language": "en", "format": "json"})
        req = Request(geo_url, headers={"User-Agent": "HOMER-Desktop/1.0"})
        with urlopen(req, timeout=8) as response:
            geo = json.loads(response.read(1_000_000).decode("utf-8"))
        results = geo.get("results") or []
        if not results:
            return {"ok": False, "error": f"No location found for {name}."}
        place = results[0]
        params = {"latitude": place["latitude"], "longitude": place["longitude"], "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m", "timezone": "auto"}
        forecast_url = "https://api.open-meteo.com/v1/forecast?" + urlencode(params)
        with urlopen(Request(forecast_url, headers={"User-Agent": "HOMER-Desktop/1.0"}), timeout=8) as response:
            weather = json.loads(response.read(1_000_000).decode("utf-8"))
        return {"ok": True, "location": {k: place.get(k) for k in ("name", "admin1", "country")}, "current": weather.get("current", {}), "units": weather.get("current_units", {}), "source": "Open-Meteo"}
    except Exception as exc:
        return {"ok": False, "error": f"Weather request failed: {exc}"}


def git_status(project_path: str = "") -> dict[str, Any]:
    """Read-only Git status for a project directory; never commits, pushes or changes branches."""
    raw = _clean_text(project_path, 500)
    target = Path(raw).expanduser() if raw else PROJECT_ROOT
    try:
        target = target.resolve(strict=True)
        allowed = [PROJECT_ROOT.resolve(), (Path.home() / "Documents").resolve()]
        if not target.is_dir() or not any(target == root or root in target.parents for root in allowed):
            return {"ok": False, "error": "Git path must be a folder inside HOMER or Documents."}
        result = subprocess.run(["git", "-C", str(target), "status", "--short", "--branch"], capture_output=True, text=True, timeout=8, check=False, shell=False)
        if result.returncode:
            return {"ok": False, "error": result.stderr.strip()[:1000] or "Git status failed."}
        return {"ok": True, "path": str(target), "status": result.stdout[:6000]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": f"Git status failed: {exc}"}



def execute_workspace_preset(name: str, confirmed: bool = False) -> dict[str, Any]:
    """Open the allowlisted URLs for a named preset only after explicit confirmation.

    Application launchers, volume, brightness, shell commands and IoT operations
    are deliberately excluded from the first safe implementation.
    """
    presets = workspace_presets()["presets"]
    key = _clean_text(name, 30).lower()
    if key not in presets:
        return {"ok": False, "error": "Unknown workspace preset."}
    if confirmed is not True:
        return {"ok": False, "requires_confirmation": True, "preset": presets[key], "message": "Confirm before opening this preset's URLs."}
    opened: list[str] = []
    failures: list[str] = []
    import webbrowser
    for url in presets[key]["urls"]:
        try:
            if webbrowser.open(url):
                opened.append(url)
            else:
                failures.append(url)
        except Exception:
            failures.append(url)
    return {"ok": not failures, "preset": key, "opened": opened, "failed": failures}


def create_code_draft(description: str, language: str = "python") -> dict[str, Any]:
    """Prepare a code-generation prompt, but never writes, compiles or executes generated code."""
    text = _clean_text(description, 2000)
    lang = _clean_text(language, 20).lower()
    if not text:
        return {"ok": False, "error": "Describe the code you need."}
    allowed = {"python", "javascript", "typescript", "html", "css", "java", "c", "cpp", "rust", "go", "sql"}
    if lang not in allowed:
        return {"ok": False, "error": "Unsupported language."}
    return {"ok": True, "language": lang, "prompt": f"Produce a safe, documented {lang} code draft for this request. Do not execute it or modify files without explicit user approval. Request: {text}"}
