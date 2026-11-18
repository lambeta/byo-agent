"""One SQLite file holds everything the agent remembers and did.

Mechanism: a single file with two FTS5 indexes kept in step by triggers, opened with
WAL so the terminal and the dashboard can write without "database is locked".

Rejected alternative: one markdown file per fact as the primary store. Readable, but
keyword search over thousands of files is slower than FTS5 and the combined mirror
still gives a person the readable view.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    start TEXT NOT NULL,
    "end" TEXT,
    attendees TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT 'user',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    subject, content, content=facts, content_rowid=id
);
CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, subject, content) VALUES (new.id, new.subject, new.content);
END;
CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, subject, content)
    VALUES ('delete', old.id, old.subject, old.content);
END;
CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, subject, content)
    VALUES ('delete', old.id, old.subject, old.content);
    INSERT INTO facts_fts(rowid, subject, content) VALUES (new.id, new.subject, new.content);
END;

CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY,
    happened_at TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
    summary, content=episodes, content_rowid=id
);
CREATE TRIGGER IF NOT EXISTS episodes_ai AFTER INSERT ON episodes BEGIN
    INSERT INTO episodes_fts(rowid, summary) VALUES (new.id, new.summary);
END;
CREATE TRIGGER IF NOT EXISTS episodes_ad AFTER DELETE ON episodes BEGIN
    INSERT INTO episodes_fts(episodes_fts, rowid, summary) VALUES ('delete', old.id, old.summary);
END;

CREATE TABLE IF NOT EXISTS chat_log (
    id INTEGER PRIMARY KEY,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    consolidated INTEGER DEFAULT 0,
    session_id TEXT DEFAULT 'default',
    source TEXT DEFAULT 'cli',
    meta TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS chat_log_session ON chat_log (session_id, id);
CREATE INDEX IF NOT EXISTS chat_log_pending ON chat_log (consolidated, id);
CREATE INDEX IF NOT EXISTS facts_subject ON facts (subject);
"""


def connect(home: Path, check_same_thread: bool = False) -> sqlite3.Connection:
    """Open the one database, creating or upgrading it in place.

    check_same_thread is off because the dashboard serves every request on its own
    thread from one connection. WAL plus the 3 s busy timeout make a read and a write
    overlap safe, and the dashboard serialises turns behind a lock.
    """
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(home / "state.db", check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive, idempotent column upgrades. SQLite has no ADD COLUMN IF NOT EXISTS."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(chat_log)").fetchall()}
    for name, ddl in (
        ("session_id", "TEXT DEFAULT 'default'"),
        ("source", "TEXT DEFAULT 'cli'"),
        ("meta", "TEXT"),
    ):
        if name not in columns:
            conn.execute(f"ALTER TABLE chat_log ADD COLUMN {name} {ddl}")
            conn.commit()
