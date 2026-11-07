"""Capa de acceso a SQLite.

Usamos una conexion por hilo (thread-local) con WAL activado. Todos los
accesos van con consultas parametrizadas: nunca se interpola SQL.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .utils import utcnow

try:  # La extension es opcional: si falla, hay busqueda vectorial de respaldo.
    import sqlite_vec

    HAS_SQLITE_VEC = True
except Exception:  # pragma: no cover - depende del entorno
    sqlite_vec = None  # type: ignore[assignment]
    HAS_SQLITE_VEC = False


SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subjects (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    color      TEXT NOT NULL DEFAULT '#6366f1',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id            TEXT PRIMARY KEY,
    subject_id    TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    original_name TEXT,
    source_type   TEXT NOT NULL,
    source_uri    TEXT,
    file_path     TEXT,
    sha256        TEXT NOT NULL UNIQUE,
    size_bytes    INTEGER NOT NULL DEFAULT 0,
    page_count    INTEGER,
    status        TEXT NOT NULL DEFAULT 'pending',
    progress      REAL NOT NULL DEFAULT 0,
    error         TEXT,
    chunk_count   INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    indexed_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_documents_subject
    ON documents(subject_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal     INTEGER NOT NULL,
    page_from   INTEGER,
    page_to     INTEGER,
    heading     TEXT,
    text        TEXT NOT NULL,
    text_norm   TEXT NOT NULL,
    n_chars     INTEGER NOT NULL,
    embedding   BLOB,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id, ordinal);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text_norm,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS conversations (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    subject_id TEXT REFERENCES subjects(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    provider        TEXT,
    model           TEXT,
    latency_ms      INTEGER,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS citations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    chunk_id    INTEGER,
    document_id TEXT,
    page_from   INTEGER,
    page_to     INTEGER,
    heading     TEXT,
    score       REAL,
    snippet     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_citations_message ON citations(message_id);
"""


_lock = threading.RLock()
_local = threading.local()
_db_path: Path | None = None


def configure(path: Path) -> None:
    """Fija la ruta de la base de datos y descarta conexiones abiertas."""
    global _db_path
    with _lock:
        _db_path = Path(path)
        _db_path.parent.mkdir(parents=True, exist_ok=True)
        _close_local()


def _close_local() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _local.conn = None


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    if HAS_SQLITE_VEC:
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)  # type: ignore[union-attr]
            conn.enable_load_extension(False)
        except Exception:
            try:
                conn.enable_load_extension(False)
            except Exception:
                pass
    return conn


def get_conn() -> sqlite3.Connection:
    if _db_path is None:
        raise RuntimeError("La base de datos no esta configurada: llama a db.configure()")
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect(_db_path)
        _local.conn = conn
    return conn


def init_db(path: Path) -> None:
    """Configura la base de datos y aplica el esquema."""
    configure(path)
    conn = get_conn()
    with _lock:
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT OR IGNORE INTO app_settings(key, value, updated_at) VALUES(?,?,?)",
            ("schema_version", str(SCHEMA_VERSION), utcnow()),
        )
        conn.commit()


def close_all() -> None:
    _close_local()


def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with _lock:
        cur = get_conn().execute(sql, params)
        return cur.fetchall()


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    with _lock:
        cur = get_conn().execute(sql, params)
        return cur.fetchone()


def execute(sql: str, params: tuple = ()) -> int:
    with _lock:
        conn = get_conn()
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.rowcount


def execute_many(sql: str, rows: list[tuple]) -> None:
    if not rows:
        return
    with _lock:
        conn = get_conn()
        conn.executemany(sql, rows)
        conn.commit()


def insert_returning_id(sql: str, params: tuple = ()) -> int:
    with _lock:
        conn = get_conn()
        cur = conn.execute(sql, params)
        conn.commit()
        return int(cur.lastrowid)


def get_setting(key: str, default: str | None = None) -> str | None:
    row = query_one("SELECT value FROM app_settings WHERE key = ?", (key,))
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    execute(
        """
        INSERT INTO app_settings(key, value, updated_at) VALUES(?,?,?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, value, utcnow()),
    )
