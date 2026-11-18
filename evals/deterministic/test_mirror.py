"""The mirror is a rendering of the store, never a second source of truth."""

from __future__ import annotations

from byo.memory.mirror import rewrite
from byo.memory.semantic.store import FactStore


def test_mirror_matches_the_store(settings, conn):
    facts = FactStore(conn)
    first = facts.add("alex", "prefers mornings")
    second = facts.add("team", "ships on thursdays")
    path = rewrite(conn, settings)
    text = path.read_text(encoding="utf-8")
    assert "[alex] prefers mornings" in text
    assert "[team] ships on thursdays" in text
    for fact_id in (first, second):
        assert (settings.memory_dir / f"{fact_id}.md").exists()
    assert "prefers mornings" in (settings.memory_dir / f"{first}.md").read_text(encoding="utf-8")


def test_forgetting_removes_the_file_and_the_line(settings, conn):
    facts = FactStore(conn)
    fact_id = facts.add("alex", "prefers mornings")
    rewrite(conn, settings)
    facts.delete(fact_id)
    rewrite(conn, settings)
    assert not (settings.memory_dir / f"{fact_id}.md").exists()
    assert "prefers mornings" not in settings.mirror_path.read_text(encoding="utf-8")
