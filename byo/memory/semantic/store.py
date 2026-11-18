"""Semantic memory: facts with full-text search.

Mechanism: rows in facts, indexed by facts_fts through triggers. Search builds an OR
query from the message's words and takes the top k by FTS rank, which is offline and
costs nothing.

Rejected alternative: embeddings. A network call and a vector store for a single-user
local agent, when the reference's own choice is keyword search.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

WORD = re.compile(r"[A-Za-z0-9_]{3,}")


def query_terms(text: str) -> list[str]:
    seen: list[str] = []
    for word in WORD.findall(text.lower()):
        if word not in seen:
            seen.append(word)
    return seen[:12]


class FactStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, subject: str, content: str, source: str = "user") -> int:
        cursor = self.conn.execute(
            "INSERT INTO facts (subject, content, source) VALUES (?, ?, ?)",
            (subject.strip(), content.strip(), source),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def get(self, fact_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM facts WHERE id = ?", (fact_id,)).fetchone()
        return dict(row) if row else None

    def update(self, fact_id: int, subject: str, content: str) -> bool:
        self.conn.execute(
            "UPDATE facts SET subject = ?, content = ? WHERE id = ?",
            (subject.strip(), content.strip(), fact_id),
        )
        self.conn.commit()
        return (
            self.conn.execute("SELECT COUNT(*) FROM facts WHERE id = ?", (fact_id,)).fetchone()[0]
            == 1
        )

    def delete(self, fact_id: int) -> bool:
        before = self.conn.total_changes
        self.conn.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
        self.conn.commit()
        return self.conn.total_changes > before

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.conn.execute("SELECT * FROM facts ORDER BY id DESC LIMIT ?", (limit,))
        ]

    def count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0])

    def search(self, text: str, k: int = 4) -> list[dict[str, Any]]:
        terms = query_terms(text)
        if not terms:
            return []
        match = " OR ".join(terms)
        try:
            rows = self.conn.execute(
                "SELECT f.* FROM facts_fts JOIN facts f ON f.id = facts_fts.rowid "
                "WHERE facts_fts MATCH ? ORDER BY rank LIMIT ?",
                (match, k),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(row) for row in rows]
