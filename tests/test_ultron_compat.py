"""Tests for HOMER's Ultron-inspired safe utility layer."""
from app.tools import ultron_compat


def test_workspace_presets_are_suggestions_only():
    result = ultron_compat.workspace_presets()
    assert result["ok"]
    assert set(result["presets"]) >= {"coding", "study", "creative", "focus"}
    assert "never launches" in result["note"]


def test_timer_validates_bounds():
    assert not ultron_compat.start_timer(0)["ok"]
    assert not ultron_compat.start_timer(86401)["ok"]
    result = ultron_compat.start_timer(1, "test")
    assert result["ok"] and result["status"] == "running"


def test_code_draft_does_not_execute_or_write():
    result = ultron_compat.create_code_draft("write a hello function", "python")
    assert result["ok"] and "Do not execute" in result["prompt"]
    assert not ultron_compat.create_code_draft("x", "powershell")["ok"]


def test_web_search_rejects_unknown_provider():
    assert not ultron_compat.web_search("example", "unknown")["ok"]


def test_read_project_file_rejects_outside_paths(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    result = ultron_compat.read_project_file(str(outside))
    assert not result["ok"]
    assert "outside" in result["error"].lower()
