"""Small SQLite-backed workspace memory inspired by Ultron's workspace recall.

This is HOMER-native code: local-only, bounded, parameterized SQL, and no
background indexing or network requests. Memory is never used as instructions.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_NOTE_CHARS = 4000
MAX_RESULTS = 10


def database_path() -> Path:
    root = Path.home() / ".homer" / "memory"
    root.mkdir(parents=True, exist_ok=True)
    return root / "workspace_memory.sqlite3"


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path(), timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL DEFAULT 'note',
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    connection.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(title, content, content='memories', content_rowid='id')"
    )
    connection.executescript("""
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
          INSERT INTO memories_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
        END;
        CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
          INSERT INTO memories_fts(memories_fts, rowid, title, content)
          VALUES ('delete', old.id, old.title, old.content);
        END;
        CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
          INSERT INTO memories_fts(memories_fts, rowid, title, content)
          VALUES ('delete', old.id, old.title, old.content);
          INSERT INTO memories_fts(rowid, title, content)
          VALUES (new.id, new.title, new.content);
        END;
    """)
    return connection


def save_memory(title: str, content: str, category: str = "note") -> dict[str, Any]:
    """Save a user-requested local note or project memory."""
    title = " ".join(str(title).split())[:160]
    content = str(content).strip()
    category = re.sub(r"[^a-z0-9_-]", "", str(category).lower())[:24] or "note"
    if not title or not content:
        return {"ok": False, "error": "A title and non-empty memory content are required."}
    if len(content) > MAX_NOTE_CHARS:
        return {"ok": False, "error": f"Memory content must be at most {MAX_NOTE_CHARS} characters."}
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        cursor = db.execute(
            "INSERT INTO memories(category,title,content,created_at,updated_at) VALUES (?,?,?,?,?)",
            (category, title, content, now, now),
        )
        memory_id = cursor.lastrowid
    return {"ok": True, "id": memory_id, "title": title, "message": "Saved locally on this device."}


def search_memories(query: str, limit: int = 5) -> dict[str, Any]:
    """Search local workspace memories using SQLite FTS5."""
    query = " ".join(str(query).split())[:200]
    limit = max(1, min(int(limit), MAX_RESULTS))
    if not query:
        return {"ok": False, "error": "Search query is required.", "results": []}
    tokens = re.findall(r"[A-Za-z0-9_]{2,}", query)
    if not tokens:
        return {"ok": True, "results": []}
    match = " AND ".join('"' + token.replace('"', '""') + '"' for token in tokens[:12])
    with _connect() as db:
        rows = db.execute(
            """SELECT m.id,m.category,m.title,m.content,m.created_at
               FROM memories_fts f JOIN memories m ON m.id=f.rowid
               WHERE memories_fts MATCH ?
               ORDER BY bm25(memories_fts), m.updated_at DESC LIMIT ?""",
            (match, limit),
        ).fetchall()
    return {"ok": True, "results": [dict(row) for row in rows]}


def delete_memory(memory_id: int) -> dict[str, Any]:
    """Delete one explicitly selected memory by ID."""
    try:
        memory_id = int(memory_id)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Memory ID must be an integer."}
    with _connect() as db:
        cursor = db.execute("DELETE FROM memories WHERE id=?", (memory_id,))
    return {"ok": cursor.rowcount == 1, "deleted": cursor.rowcount == 1, "id": memory_id}


def list_recent_memories(limit: int = 10) -> dict[str, Any]:
    """List recent memory titles; content is not returned unless searched."""
    limit = max(1, min(int(limit), MAX_RESULTS))
    with _connect() as db:
        rows = db.execute(
            "SELECT id,category,title,created_at FROM memories ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return {"ok": True, "results": [dict(row) for row in rows]}
