"""Tests for HOMER's local workspace memory and reminder storage."""
from app.memory import workspace
from app.tasks import reminders


def test_memory_save_search_and_delete(monkeypatch, tmp_path):
    monkeypatch.setattr(workspace, "database_path", lambda: tmp_path / "memory.sqlite3")
    saved = workspace.save_memory("Project notes", "HOMER uses SQLite FTS5 for local workspace recall.", "project")
    assert saved["ok"] is True
    found = workspace.search_memories("SQLite FTS5 workspace")
    assert found["ok"] is True
    assert len(found["results"]) == 1
    assert found["results"][0]["title"] == "Project notes"
    deleted = workspace.delete_memory(saved["id"])
    assert deleted["deleted"] is True
    assert workspace.search_memories("SQLite FTS5")["results"] == []


def test_memory_bounds_and_empty_validation(monkeypatch, tmp_path):
    monkeypatch.setattr(workspace, "database_path", lambda: tmp_path / "memory.sqlite3")
    assert workspace.save_memory("", "content")["ok"] is False
    assert workspace.save_memory("title", "x" * 4001)["ok"] is False


def test_reminder_create_complete_and_listing(monkeypatch, tmp_path):
    monkeypatch.setattr(reminders, "database_path", lambda: tmp_path / "reminders.sqlite3")
    created = reminders.create_reminder("Take a break", 5)
    assert created["ok"] is True
    assert len(reminders.list_reminders()["reminders"]) == 1
    completed = reminders.complete_reminder(created["id"])
    assert completed["completed"] is True
    assert reminders.list_reminders()["reminders"] == []


def test_reminder_rejects_invalid_delays(monkeypatch, tmp_path):
    monkeypatch.setattr(reminders, "database_path", lambda: tmp_path / "reminders.sqlite3")
    assert reminders.create_reminder("test", 0)["ok"] is False
    assert reminders.create_reminder("test", 600000)["ok"] is False
