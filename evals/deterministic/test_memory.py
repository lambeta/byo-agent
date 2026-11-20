"""Semantic and episodic stores, and one turn that actually recalls."""

from __future__ import annotations

from scripted import script, text

from byo.app import Agent
from byo.memory.episodic.store import EpisodeStore
from byo.memory.semantic.store import FactStore

GATE_YES = {
    "text": '{"needs_memory": true, "reason": "asks about a person"}',
    "stop_reason": "end_turn",
    "usage": {"in": 10, "out": 10},
}


def test_fact_store_write_read_update_delete(conn):
    facts = FactStore(conn)
    fact_id = facts.add("alex", "prefers morning meetings")
    assert facts.count() == 1
    assert facts.get(fact_id)["subject"] == "alex"
    assert facts.update(fact_id, "alex", "prefers afternoons")
    assert facts.search("afternoons")[0]["content"] == "prefers afternoons"
    assert facts.delete(fact_id) is True
    assert facts.count() == 0


def test_search_is_bounded_by_k(conn):
    facts = FactStore(conn)
    for index in range(6):
        facts.add("alex", f"prefers mornings number {index}")
    assert len(facts.search("mornings", k=4)) == 4


def test_search_ignores_unusable_text(conn):
    assert FactStore(conn).search("?!", k=4) == []


def test_episode_store(conn):
    episodes = EpisodeStore(conn)
    episodes.add("2026-11-18", "booked a catch-up with alex")
    assert episodes.count() == 1
    assert "catch-up" in episodes.search("catch-up")[0]["summary"]


def test_episode_list_is_newest_first_and_bounded(conn):
    episodes = EpisodeStore(conn)
    for day in ("2026-11-17", "2026-11-18", "2026-11-19"):
        episodes.add(day, f"summary of {day}")
    assert [row["happened_at"] for row in episodes.list()] == [
        "2026-11-19",
        "2026-11-18",
        "2026-11-17",
    ]
    assert len(episodes.list(limit=2)) == 2


def test_episode_search_ignores_unusable_text(conn):
    episodes = EpisodeStore(conn)
    episodes.add("2026-11-18", "booked a catch-up with alex")
    assert episodes.search("?!") == []


def test_episode_search_survives_a_missing_fts_index(conn):
    # A database created before the FTS tables existed degrades to no hits, not an error.
    episodes = EpisodeStore(conn)
    episodes.add("2026-11-18", "booked a catch-up with alex")
    conn.execute("DROP TABLE episodes_fts")
    assert episodes.search("catch-up") == []


def test_fact_search_survives_a_missing_fts_index(conn):
    facts = FactStore(conn)
    facts.add("alex", "prefers morning meetings")
    conn.execute("DROP TABLE facts_fts")
    assert facts.search("mornings") == []


def test_a_turn_recalls_a_fact_and_records_the_gate(settings):
    adapter = script(GATE_YES, text("Alex prefers mornings."))
    agent = Agent(settings, adapter=adapter)
    agent.memory.facts.add("alex", "prefers morning meetings")
    result = agent.respond("when should I book alex?")
    assert result.reply == "Alex prefers mornings."
    assert "prefers morning meetings" in adapter.calls[1].system
    events = [event for event in agent.trajectory.events if event["type"] == "gate"]
    assert events[0]["decision"] == "retrieve"
    agent.close()


def test_recall_falls_back_to_episodes_when_facts_miss(settings, conn):
    from byo.memory import Memory

    memory = Memory(conn, settings, script())
    memory.episodes.add("2026-11-18", "booked a catch-up with alex")
    memory.retrieve = True
    block = memory.recall_block("when was the catch-up?")
    assert block == "- 2026-11-18: booked a catch-up with alex"
