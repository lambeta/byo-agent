"""The one database: schema, pragmas, triggers and idempotent open."""

from __future__ import annotations

from byo.db import connect


def test_schema_objects_exist(conn):
    names = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master")}
    for expected in (
        "calendar_events",
        "facts",
        "facts_fts",
        "episodes",
        "episodes_fts",
        "chat_log",
        "facts_ai",
        "facts_ad",
        "facts_au",
        "episodes_ai",
        "episodes_ad",
    ):
        assert expected in names


def test_wal_and_busy_timeout(conn):
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 3000


def test_second_open_is_idempotent(settings):
    first = connect(settings.home)
    first.close()
    second = connect(settings.home)
    columns = {row[1] for row in second.execute("PRAGMA table_info(chat_log)")}
    assert {"session_id", "source", "meta"} <= columns
    second.close()


def test_fact_triggers_keep_the_index_in_step(conn):
    conn.execute("INSERT INTO facts (subject, content) VALUES ('alex', 'prefers mornings')")
    conn.commit()
    hits = conn.execute("SELECT content FROM facts_fts WHERE facts_fts MATCH 'mornings'").fetchall()
    assert [row["content"] for row in hits] == ["prefers mornings"]
    conn.execute("DELETE FROM facts")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM facts_fts").fetchone()[0] == 0


def test_a_legacy_chat_log_is_upgraded_in_place(settings):
    # A database from before the session_id/source/meta columns existed keeps its
    # rows and gains the columns on open.
    import sqlite3

    path = settings.home / "state.db"
    raw = sqlite3.connect(path)
    raw.execute(
        "CREATE TABLE chat_log (id INTEGER PRIMARY KEY, role TEXT NOT NULL,"
        " content TEXT NOT NULL, consolidated INTEGER DEFAULT 0,"
        " created_at TEXT DEFAULT (datetime('now')))"
    )
    raw.execute("INSERT INTO chat_log (role, content) VALUES ('user', 'hello')")
    raw.commit()
    raw.close()

    conn = connect(settings.home)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(chat_log)")}
    assert {"session_id", "source", "meta"} <= columns
    row = conn.execute("SELECT role, content, session_id, source, meta FROM chat_log").fetchone()
    assert (row["role"], row["content"]) == ("user", "hello")
    assert (row["session_id"], row["source"], row["meta"]) == ("default", "cli", None)
    conn.close()
