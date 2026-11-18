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
