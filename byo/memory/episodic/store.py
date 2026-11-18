"""Episodic memory: dated summaries of what happened."""

from __future__ import annotations

import sqlite3
from typing import Any

from byo.memory.semantic.store import query_terms


class EpisodeStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, happened_at: str, summary: str) -> int:
        cursor = self.conn.execute(
            "INSERT INTO episodes (happened_at, summary) VALUES (?, ?)",
            (happened_at, summary.strip()),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM episodes ORDER BY id DESC LIMIT ?", (limit,)
            )
        ]

    def count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0])

    def search(self, text: str, k: int = 2) -> list[dict[str, Any]]:
        terms = query_terms(text)
        if not terms:
            return []
        try:
            rows = self.conn.execute(
                "SELECT e.* FROM episodes_fts JOIN episodes e ON e.id = episodes_fts.rowid "
                "WHERE episodes_fts MATCH ? ORDER BY rank LIMIT ?",
                (" OR ".join(terms), k),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(row) for row in rows]
