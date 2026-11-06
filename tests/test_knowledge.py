"""Tests for HOMER's local RAG and speech settings."""
from app.knowledge.context import build_knowledge_context
from app.knowledge.store import index_knowledge_base, search_knowledge, knowledge_status
from app.voice.speech_settings import speech_rate, speech_speed


def test_indexes_project_and_user_documents_incrementally(tmp_path):
    project = tmp_path / "project"
    docs = tmp_path / "documents"
    project.mkdir()
    docs.mkdir()
    (project / "README.md").write_text(
        "HOMER uses a Groq API and a local desktop application.", encoding="utf-8"
    )
    (docs / "notes.txt").write_text(
        "The water quality project measures pH and temperature using sensors.", encoding="utf-8"
    )
    (project / ".env").write_text("GROQ_API_KEY=must-not-be-indexed", encoding="utf-8")
    (project / "node_modules").mkdir()
    (project / "node_modules" / "package.json").write_text("secret package", encoding="utf-8")
    database = tmp_path / "knowledge.sqlite3"

    first = index_knowledge_base(project, database, docs)
    assert first["indexed"] == 2
    assert first["documents"] == 2
    assert first["chunks"] >= 2

    project_hits = search_knowledge("Groq API local desktop", db_path=database)
    assert project_hits
    assert project_hits[0].source_type == "project"
    assert "Groq" in project_hits[0].chunk

    document_hits = search_knowledge("water quality pH temperature sensors", db_path=database)
    assert document_hits
    assert document_hits[0].source_type == "document"
    assert document_hits[0].title == "notes.txt"

    second = index_knowledge_base(project, database, docs)
    assert second["indexed"] == 0
    assert second["documents"] == 2

    (docs / "notes.txt").write_text("The project now measures turbidity and dissolved oxygen.", encoding="utf-8")
    third = index_knowledge_base(project, database, docs)
    assert third["indexed"] == 1
    updated_hits = search_knowledge("turbidity dissolved oxygen", db_path=database)
    assert updated_hits
    assert "turbidity" in updated_hits[0].chunk.lower()

    status = knowledge_status(database)
    assert status["documents"] == 2


def test_search_empty_or_stopword_only_query_returns_no_results(tmp_path):
    database = tmp_path / "empty.sqlite3"
    assert search_knowledge("", db_path=database) == []
    assert search_knowledge("what is the", db_path=database) == []


def test_context_marks_sources_as_untrusted_and_citable(tmp_path):
    project = tmp_path / "repo"
    docs = tmp_path / "docs"
    project.mkdir()
    docs.mkdir()
    (docs / "guide.md").write_text("The test feature uses SQLite FTS5 retrieval.", encoding="utf-8")
    database = tmp_path / "ctx.sqlite3"
    index_knowledge_base(project, database, docs)
    results = search_knowledge("SQLite FTS5 retrieval", db_path=database)
    context = build_knowledge_context(results)
    assert "untrusted source material" in context
    assert "[Source: guide.md (document)]" in context
    assert "SQLite FTS5" in context


def test_speech_speed_defaults_to_one_point_five(monkeypatch):
    monkeypatch.delenv("HOMER_TTS_SPEED", raising=False)
    assert speech_speed() == 1.5
    assert speech_rate() == 248


def test_speech_speed_is_configurable_and_validated(monkeypatch):
    monkeypatch.setenv("HOMER_TTS_SPEED", "1.25")
    assert speech_rate() == 206
    monkeypatch.setenv("HOMER_TTS_SPEED", "2.5")
    try:
        speech_rate()
    except ValueError as exc:
        assert "between 0.75 and 2.00" in str(exc)
    else:
        raise AssertionError("Out-of-range speed should fail validation")
