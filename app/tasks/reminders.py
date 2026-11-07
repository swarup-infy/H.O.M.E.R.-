"""Local reminders and timers for HOMER. No OS scheduler, shell, or network required."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

MAX_TITLE = 160
MAX_ITEMS = 30


def database_path() -> Path:
    root = Path.home() / ".homer" / "tasks"
    root.mkdir(parents=True, exist_ok=True)
    return root / "reminders.sqlite3"


def _connect() -> sqlite3.Connection:
    db = sqlite3.connect(database_path(), timeout=5.0)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        due_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        completed INTEGER NOT NULL DEFAULT 0
    )""")
    return db


def create_reminder(title: str, minutes_from_now: int) -> dict[str, Any]:
    """Create a one-shot local reminder. The app must be running to notify."""
    title = " ".join(str(title).split())[:MAX_TITLE]
    try:
        minutes = int(minutes_from_now)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Reminder delay must be whole minutes."}
    if not title:
        return {"ok": False, "error": "Reminder title cannot be blank."}
    if not 1 <= minutes <= 525600:
        return {"ok": False, "error": "Reminder must be between 1 minute and 365 days from now."}
    now = datetime.now(timezone.utc)
    due = now + timedelta(minutes=minutes)
    with _connect() as db:
        cursor = db.execute(
            "INSERT INTO reminders(title,due_at,created_at) VALUES(?,?,?)",
            (title, due.isoformat(), now.isoformat()),
        )
    return {"ok": True, "id": cursor.lastrowid, "title": title, "due_at": due.isoformat(),
            "message": "Reminder saved locally. HOMER must be running to show the notification."}


def list_reminders(include_completed: bool = False) -> dict[str, Any]:
    """List upcoming and overdue reminders."""
    with _connect() as db:
        if include_completed:
            rows = db.execute("SELECT * FROM reminders ORDER BY due_at LIMIT ?", (MAX_ITEMS,)).fetchall()
        else:
            rows = db.execute("SELECT * FROM reminders WHERE completed=0 ORDER BY due_at LIMIT ?", (MAX_ITEMS,)).fetchall()
    return {"ok": True, "reminders": [dict(row) for row in rows]}


def due_reminders() -> list[dict[str, Any]]:
    """Return due reminders; marks them complete to prevent duplicate notifications."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        rows = db.execute(
            "SELECT * FROM reminders WHERE completed=0 AND due_at<=? ORDER BY due_at LIMIT ?",
            (now, MAX_ITEMS),
        ).fetchall()
        if rows:
            db.executemany("UPDATE reminders SET completed=1 WHERE id=?", [(r["id"],) for r in rows])
    return [dict(row) for row in rows]


def complete_reminder(reminder_id: int) -> dict[str, Any]:
    """Dismiss a saved reminder by ID."""
    try:
        reminder_id = int(reminder_id)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Reminder ID must be an integer."}
    with _connect() as db:
        cursor = db.execute("UPDATE reminders SET completed=1 WHERE id=?", (reminder_id,))
    return {"ok": cursor.rowcount == 1, "id": reminder_id, "completed": cursor.rowcount == 1}


def create_timer(label: str, seconds: int) -> dict[str, Any]:
    """Create a one-shot timer using the same persistent reminder store."""
    try:
        value = int(seconds)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Timer duration must be an integer number of seconds."}
    if not 1 <= value <= 7 * 24 * 3600:
        return {"ok": False, "error": "Timer must be between 1 second and 7 days."}
    minutes = max(1, (value + 59) // 60)
    return create_reminder(label or "Timer finished", minutes)
