"""Visible, isolated browser automation for HOMER.

Playwright controls a dedicated HOMER browser profile, never the user's normal
Chrome/Edge profile. Only public HTTPS websites on an explicit domain allowlist
are navigated. No arbitrary JavaScript, cookie export, or credential scraping.
"""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ALLOWED_DOMAINS = {
    "youtube.com", "youtu.be", "spotify.com", "google.com", "google.co.in",
    "wikipedia.org", "github.com", "reddit.com", "chatgpt.com", "openai.com",
    "netflix.com", "twitch.tv", "linkedin.com", "instagram.com", "x.com",
    "facebook.com", "amazon.com", "amazon.in", "microsoft.com", "outlook.com",
    "live.com", "gmail.com", "discord.com", "notion.so", "stackoverflow.com",
    "claude.ai", "perplexity.ai", "brave.com",
}
BLOCKED_CLICK_TERMS = {
    "buy now", "place order", "delete account", "delete permanently",
    "send money", "transfer", "pay now", "purchase", "confirm payment",
    "sign out", "log out", "remove account",
}
_lock = threading.RLock()
_browser_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="homer-browser")
_playwright = None
_context = None
_pages: list[Any] = []
_active_index = 0


def _allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme != "https" or not parsed.hostname:
            return False
        host = parsed.hostname.casefold()
        return any(host == domain or host.endswith("." + domain) for domain in ALLOWED_DOMAINS)
    except ValueError:
        return False


def _ensure_browser():
    global _playwright, _context, _pages
    if _context is not None:
        _pages = [page for page in _context.pages if not page.is_closed()]
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Browser automation is not installed. Run: python -m pip install playwright "
            "and python -m playwright install chromium"
        ) from exc
    profile = Path(os.getenv("HOMER_BROWSER_PROFILE", str(Path.home() / ".homer" / "browser-profile"))).expanduser()
    profile.mkdir(parents=True, exist_ok=True)
    _playwright = sync_playwright().start()
    try:
        _context = _playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            headless=False,
            viewport=None,
            args=["--start-maximized", "--disable-session-crashed-bubble"],
        )
    except Exception:
        _playwright.stop()
        _playwright = None
        raise
    _pages = [page for page in _context.pages if not page.is_closed()]
    if not _pages:
        _pages = [_context.new_page()]


def _page(tab_index: int = -1):
    global _active_index
    _ensure_browser()
    if not _pages:
        _pages.append(_context.new_page())
    if tab_index == -1:
        tab_index = _active_index
    if not isinstance(tab_index, int) or isinstance(tab_index, bool) or not 0 <= tab_index < len(_pages):
        raise ValueError("tab_index is outside the current tab list.")
    return _pages[tab_index]


def _tabs() -> list[dict[str, Any]]:
    global _active_index
    _ensure_browser()
    _active_index = min(_active_index, max(0, len(_pages) - 1))
    return [
        {"tab_index": i, "title": page.title()[:160], "url": page.url, "active": i == _active_index}
        for i, page in enumerate(_pages)
    ]


def _media_action(page, action: str, value: float | None = None) -> dict[str, Any]:
    result = page.evaluate(
        """async ({action, value}) => {
          const media = [...document.querySelectorAll('video, audio')];
          if (!media.length) return {ok:false, error:'No HTML audio/video player was found on this page.'};
          const el = media.find(item => !item.paused) || media[0];
          try {
            if (action === 'play') await el.play();
            else if (action === 'pause') el.pause();
            else if (action === 'toggle') { if (el.paused) await el.play(); else el.pause(); }
            else if (action === 'stop') { el.pause(); el.currentTime = 0; }
            else if (action === 'volume') { el.volume = Math.max(0, Math.min(1, value)); el.muted = false; }
            else if (action === 'volume_up') { el.volume = Math.min(1, el.volume + 0.1); el.muted = false; }
            else if (action === 'volume_down') { el.volume = Math.max(0, el.volume - 0.1); }
            else if (action === 'seek') el.currentTime = Math.max(0, Math.min(Number(value) || 0, Number.isFinite(el.duration) ? el.duration : 86400));
            return {ok:true, paused:el.paused, muted:el.muted, volume:Math.round(el.volume*100),
                    current_time:Math.floor(el.currentTime || 0),
                    duration:Number.isFinite(el.duration) ? Math.floor(el.duration) : null,
                    player_count:media.length};
          } catch (error) {
            return {ok:false, error:'The website blocked this media action: ' + String(error).slice(0,160)};
          }
        }""",
        {"action": action, "value": value},
    )
    return result


def _browser_action_impl(
    action: str,
    url: str = "",
    text: str = "",
    tab_index: int = -1,
    volume: int = 50,
    seconds: int = 0,
) -> dict[str, Any]:
    """Perform one validated action in HOMER's visible browser."""
    global _active_index
    valid_actions = {
        "open", "navigate", "back", "forward", "reload", "tabs", "new_tab", "select_tab", "close_tab",
        "snapshot", "click_text", "type_text", "press_key",
        "play", "pause", "toggle", "stop", "volume", "volume_up",
        "volume_down", "seek",
    }
    if action not in valid_actions:
        return {"ok": False, "error": "Unsupported browser action."}
    if action in {"navigate", "new_tab"} and not _allowed_url(url):
        return {"ok": False, "error": "Only allowlisted HTTPS sites can be opened in HOMER's browser."}
    with _lock:
        try:
            if action == "tabs":
                return {"ok": True, "tabs": _tabs()}
            if action == "open":
                _ensure_browser()
                return {"ok": True, "tabs": _tabs(), "message": "HOMER's browser is open and visible."}
            if action == "new_tab":
                if url and not _allowed_url(url):
                    return {"ok": False, "error": "Only allowlisted HTTPS sites can be opened."}
                _ensure_browser()
                page = _context.new_page()
                _pages.append(page)
                _active_index = len(_pages) - 1
                page.bring_to_front()
                if url:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                return {"ok": True, "tabs": _tabs()}
            page = _page(tab_index)
            if action == "navigate":
                if not _allowed_url(url):
                    return {"ok": False, "error": "Only allowlisted HTTPS sites can be opened in HOMER's browser."}
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                return {"ok": True, "title": page.title()[:160], "url": page.url}
            if action == "back":
                page.go_back(wait_until="domcontentloaded", timeout=15000)
                return {"ok": True, "title": page.title()[:160], "url": page.url}
            if action == "forward":
                page.go_forward(wait_until="domcontentloaded", timeout=15000)
                return {"ok": True, "title": page.title()[:160], "url": page.url}
            if action == "reload":
                page.reload(wait_until="domcontentloaded", timeout=15000)
                return {"ok": True, "title": page.title()[:160], "url": page.url}
            if action == "select_tab":
                _active_index = tab_index
                page.bring_to_front()
                return {"ok": True, "selected_tab": tab_index, "title": page.title()[:160]}
            if action == "close_tab":
                if len(_pages) == 1:
                    page.goto("about:blank")
                    return {"ok": True, "message": "Kept the last browser tab open and cleared its page."}
                page.close()
                _pages[:] = [p for p in _context.pages if not p.is_closed()]
                _active_index = min(_active_index, max(0, len(_pages) - 1))
                if _pages:
                    _pages[_active_index].bring_to_front()
                return {"ok": True, "tabs": _tabs()}
            if action == "snapshot":
                return {
                    "ok": True, "title": page.title()[:160], "url": page.url,
                    "content": page.locator("body").inner_text(timeout=8000)[:12000],
                }
            if action == "click_text":
                label = text.strip()
                if not label or len(label) > 160:
                    return {"ok": False, "error": "Provide a visible text label of 1-160 characters."}
                if any(term in label.casefold() for term in BLOCKED_CLICK_TERMS):
                    return {"ok": False, "error": "This action requires the user to complete it manually for safety."}
                locator = page.get_by_text(label, exact=True)
                count = locator.count()
                if count != 1:
                    return {"ok": False, "error": f"Expected one exact match, found {count}. Use a more specific label."}
                locator.click(timeout=7000)
                return {"ok": True, "clicked": label}
            if action == "type_text":
                if len(text) > 2000:
                    return {"ok": False, "error": "Text is limited to 2,000 characters per action."}
                page.keyboard.insert_text(text)
                return {"ok": True, "typed_characters": len(text), "note": "Text was typed into the currently focused browser element; it was not submitted."}
            if action == "press_key":
                if text not in {"Enter", "Escape", "Tab", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space", "Home", "End", "PageUp", "PageDown", "Control+L", "Control+T", "Control+W", "Control+Tab", "Control+Shift+Tab"}:
                    return {"ok": False, "error": "That browser key is not on HOMER's keyboard allowlist."}
                page.keyboard.press(text)
                return {"ok": True, "key": text}
            if action in {"play", "pause", "toggle", "stop", "volume_up", "volume_down"}:
                return _media_action(page, action)
            if action == "volume":
                if not 0 <= volume <= 100:
                    return {"ok": False, "error": "Volume must be between 0 and 100."}
                return _media_action(page, action, volume / 100)
            if action == "seek":
                if not 0 <= seconds <= 86400:
                    return {"ok": False, "error": "Seek position must be between 0 and 86,400 seconds."}
                return _media_action(page, action, seconds)
        except Exception as exc:
            return {"ok": False, "error": "Browser action failed (" + type(exc).__name__ + "): " + str(exc)[:180]}
    return {"ok": False, "error": "Browser action was not completed."}


def _close_browser_impl() -> dict[str, Any]:
    """Close only HOMER's dedicated browser context."""
    global _playwright, _context, _pages, _active_index
    with _lock:
        try:
            if _context is not None:
                _context.close()
            if _playwright is not None:
                _playwright.stop()
            _context = None
            _playwright = None
            _pages = []
            _active_index = 0
            return {"ok": True, "message": "Closed HOMER's dedicated browser."}
        except Exception as exc:
            return {"ok": False, "error": "Could not close HOMER's browser (" + type(exc).__name__ + ")."}



def browser_action(
    action: str,
    url: str = "",
    text: str = "",
    tab_index: int = -1,
    volume: int = 50,
    seconds: int = 0,
) -> dict[str, Any]:
    """Serialize every Playwright operation onto one dedicated browser thread."""
    return _browser_executor.submit(
        _browser_action_impl, action, url, text, tab_index, volume, seconds
    ).result()


def close_browser() -> dict[str, Any]:
    """Close the dedicated browser on the same thread that owns its Playwright runtime."""
    return _browser_executor.submit(_close_browser_impl).result()


def _reset_for_tests() -> None:
    """Reset lazy browser globals; tests must mock Playwright and never launch a real browser."""
    global _playwright, _context, _pages, _active_index
    _active_index = 0
    _playwright = None
    _context = None
    _pages = []
