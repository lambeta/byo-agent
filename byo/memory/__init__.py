"""Memory facade: the gate decides, retrieval reads, consolidation writes.

Mechanism: one object the app holds. Every capability is a small module behind it;
this file only sequences them.

Rejected alternative: letting the session reach into SQLite directly. The gate and the
consolidation would then be optional conventions rather than one seam.
"""

from __future__ import annotations

from typing import Any

from byo.memory import consolidation as consolidation_mod
from byo.memory import mirror as mirror_mod
from byo.memory.episodic.store import EpisodeStore
from byo.memory.retrieval_gate import decide
from byo.memory.semantic.store import FactStore


class Memory:
    def __init__(self, conn, settings, adapter) -> None:
        self.conn = conn
        self.settings = settings
        self.adapter = adapter
        self.facts = FactStore(conn)
        self.episodes = EpisodeStore(conn)
        self.retrieve = True
        self.last_gate: dict[str, Any] = {}

    def gate(self, message: str) -> dict[str, Any]:
        self.last_gate = decide(
            self.adapter, self.settings.effective_small_model(), message, self.settings.max_tokens
        )
        self.retrieve = self.last_gate.get("decision") == "retrieve"
        return self.last_gate

    def recall_block(self, message: str) -> str:
        if not self.retrieve or not message.strip():
            return ""
        hits = self.facts.search(message, self.settings.retrieval_top_k)
        if hits:
            return "\n".join(f"- [{row['subject']}] {row['content']}" for row in hits)
        episodes = self.episodes.search(message, 2)
        if episodes:
            return "\n".join(f"- {row['happened_at']}: {row['summary']}" for row in episodes)
        return ""

    def maybe_consolidate(self, recalled: str = "") -> dict[str, Any] | None:
        pending = len(consolidation_mod.pending_rows(self.conn))
        if pending < self.settings.consolidate_every:
            return None
        note = consolidation_mod.consolidate(
            self.conn,
            self.adapter,
            self.settings.effective_small_model(),
            self.facts,
            self.episodes,
            recalled=recalled,
            max_tokens=self.settings.max_tokens,
        )
        if note:
            self.rewrite_mirror()
        return note

    def rewrite_mirror(self):
        return mirror_mod.rewrite(self.conn, self.settings)
