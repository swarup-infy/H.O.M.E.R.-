"""SQLite FTS5 knowledge store for user documents and HOMER source files.

The index is local, incremental, and CPU/RAM friendly. FTS5 provides ranked
lexical retrieval without downloading a heavyweight embedding model or running
a local LLM. Results are passed to Groq as untrusted reference material.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".txt", ".md", ".rst", ".py", ".js", ".jsx", ".ts",
    ".tsx", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".csv",
    ".html", ".css", ".sql", ".ps1", ".bat", ".sh", ".log",
}
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", "node_modules",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
    "site-packages", "uploads", "vector_db", "knowledge_db", ".next",
}
EXCLUDED_NAMES = {
    ".env", ".env.local", ".env.production", "secrets.json", "credentials.json",
    "id_rsa", "id_ed25519",
}
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_FILES_PER_SCAN = 5000
CHUNK_CHARS = 1100
CHUNK_OVERLAP = 160


@dataclass(frozen=True)
class SearchResult:
    title: str
    source_type: str
    source_path: str
    chunk: str
    score: float

    def as_dict(self) -> dict:
        return asdict(self)


def database_path() -> Path:
    override = os.getenv("HOMER_KNOWLEDGE_DB", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".homer" / "knowledge" / "knowledge.sqlite3"


def default_document_dir() -> Path:
    override = os.getenv("HOMER_KNOWLEDGE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".homer" / "knowledge" / "documents"


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            source_path TEXT NOT NULL UNIQUE,
            source_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            content, title, source_path UNINDEXED, source_type UNINDEXED,
            chunk_id UNINDEXED, tokenize='unicode61'
        );
        """
    )
    return connection


def _read_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF indexing requires pypdf. Install it with: python -m pip install pypdf") from exc
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("DOCX indexing requires python-docx. Install it with: python -m pip install python-docx") from exc
        document = Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    return path.read_text(encoding="utf-8", errors="replace")


def _chunks(text: str) -> list[str]:
    text = text.replace("\x00", " ").replace("\r\n", "\n").strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_CHARS, len(text))
        if end < len(text):
            boundary = max(text.rfind("\n", start, end), text.rfind(". ", start, end), text.rfind(" ", start, end))
            if boundary > start + CHUNK_CHARS // 2:
                end = boundary + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)
    return chunks


def _iter_files(root: Path) -> Iterable[Path]:
    if not root.exists() or not root.is_dir():
        return
    count = 0
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith("."))
        for name in sorted(names):
            path = Path(current) / name
            if name.lower() in EXCLUDED_NAMES or name.lower().startswith(".env"):
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield path
            count += 1
            if count >= MAX_FILES_PER_SCAN:
                return


def _index_file(connection: sqlite3.Connection, path: Path, source_type: str) -> bool:
    try:
        raw = _read_file(path)
    except (OSError, ValueError, RuntimeError):
        return False
    text = raw.strip()
    if not text:
        return False
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    source_path = str(path.resolve())
    existing = connection.execute(
        "SELECT id, content_hash FROM documents WHERE source_path = ?", (source_path,)
    ).fetchone()
    if existing and existing["content_hash"] == digest:
        return False
    title = path.name
    if existing:
        doc_id = existing["id"]
        old_ids = [row["id"] for row in connection.execute(
            "SELECT id FROM chunks WHERE document_id = ?", (doc_id,)
        )]
        if old_ids:
            connection.executemany("DELETE FROM chunks_fts WHERE chunk_id = ?", [(str(i),) for i in old_ids])
        connection.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
        connection.execute(
            "UPDATE documents SET source_type=?, title=?, content_hash=?, indexed_at=CURRENT_TIMESTAMP WHERE id=?",
            (source_type, title, digest, doc_id),
        )
    else:
        cursor = connection.execute(
            "INSERT INTO documents(source_path, source_type, title, content_hash) VALUES (?, ?, ?, ?)",
            (source_path, source_type, title, digest),
        )
        doc_id = cursor.lastrowid
    for index, chunk in enumerate(_chunks(text)):
        cursor = connection.execute(
            "INSERT INTO chunks(document_id, chunk_index, content) VALUES (?, ?, ?)",
            (doc_id, index, chunk),
        )
        chunk_id = cursor.lastrowid
        connection.execute(
            "INSERT INTO chunks_fts(content, title, source_path, source_type, chunk_id) VALUES (?, ?, ?, ?, ?)",
            (chunk, title, source_path, source_type, str(chunk_id)),
        )
    return True


def index_knowledge_base(project_root: str | Path | None = None, db_path: Path | None = None, document_dir: str | Path | None = None) -> dict:
    """Index project code/docs and the user's local document folder incrementally."""
    root = Path(project_root).resolve() if project_root else Path(__file__).resolve().parents[2]
    docs = Path(document_dir).expanduser().resolve() if document_dir else default_document_dir().resolve()
    docs.mkdir(parents=True, exist_ok=True)
    indexed = skipped = errors = 0
    with _connect(db_path) as connection:
        for source_type, folder in (("project", root), ("document", docs)):
            for path in _iter_files(folder):
                try:
                    changed = _index_file(connection, path, source_type)
                    indexed += int(changed)
                    skipped += int(not changed)
                except Exception:
                    errors += 1
        connection.commit()
        totals = connection.execute(
            "SELECT COUNT(DISTINCT d.id) AS documents, COUNT(c.id) AS chunks "
            "FROM documents d LEFT JOIN chunks c ON c.document_id=d.id"
        ).fetchone()
    return {
        "indexed": indexed, "unchanged_or_empty": skipped, "errors": errors,
        "documents": totals["documents"], "chunks": totals["chunks"],
        "document_directory": str(docs),
    }


def search_knowledge(query: str, limit: int = 5, db_path: Path | None = None) -> list[SearchResult]:
    """Retrieve ranked chunks using SQLite FTS5 BM25; malformed queries fail closed."""
    stop_words = {"what", "when", "where", "which", "who", "why", "how", "the", "and", "for", "with", "from", "that", "this", "are", "was", "were", "is", "a", "an", "to", "of", "in", "on", "at", "it", "my", "your", "about", "please", "can", "you"}
    terms = [term for term in re.findall(r"[\w]{2,}", query.casefold()) if term not in stop_words][:20]
    if not terms:
        return []
    unique_terms = list(dict.fromkeys(terms))
    phrase_and = " AND ".join('"' + term.replace('"', '""') + '"' for term in unique_terms)
    phrase_or = " OR ".join('"' + term.replace('"', '""') + '"' for term in unique_terms)
    try:
        with _connect(db_path) as connection:
            sql = """SELECT f.title, f.source_type, f.source_path, f.content,
                            bm25(chunks_fts, 1.0, 0.4) AS rank
                     FROM chunks_fts f WHERE chunks_fts MATCH ?
                     ORDER BY rank LIMIT ?"""
            rows = connection.execute(sql, (phrase_and, max(1, min(int(limit), 10)))).fetchall()
            if not rows and len(unique_terms) > 1:
                rows = connection.execute(sql, (phrase_or, max(1, min(int(limit), 10)))).fetchall()
    except sqlite3.OperationalError:
        return []
    return [SearchResult(
        title=row["title"], source_type=row["source_type"],
        source_path=row["source_path"], chunk=row["content"],
        score=float(row["rank"]),
    ) for row in rows]


def knowledge_status(db_path: Path | None = None) -> dict:
    """Return safe index counts and the local documents folder."""
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT COUNT(DISTINCT d.id) AS documents, COUNT(c.id) AS chunks "
            "FROM documents d LEFT JOIN chunks c ON c.document_id=d.id"
        ).fetchone()
    return {
        "documents": row["documents"], "chunks": row["chunks"],
        "document_directory": str(default_document_dir()),
    }
