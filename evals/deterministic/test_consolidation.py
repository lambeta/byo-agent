"""Consolidation: schedule, marking, suppression and failure containment."""

from __future__ import annotations

import json

from scripted import script, text

from byo.memory.consolidation import consolidate, pending_rows
from byo.memory.episodic.store import EpisodeStore
from byo.memory.semantic.store import FactStore


def seed(conn, count=6):
    for index in range(count):
        conn.execute(
            "INSERT INTO chat_log (role, content, session_id) VALUES (?, ?, 'default')",
            ("user" if index % 2 == 0 else "assistant", f"message {index}"),
        )
    conn.commit()


def answer(payload: dict) -> dict:
    return {"text": json.dumps(payload), "usage": {"in": 30, "out": 20}}


def test_consolidation_keeps_facts_and_one_episode(conn):
    seed(conn)
    facts, episodes = FactStore(conn), EpisodeStore(conn)
    payload = {
        "facts": [
            {"subject": "alex", "content": "prefers morning meetings"},
            {"subject": "project", "content": "ship by december"},
        ],
        "episode": "planned the december launch",
    }
    note = consolidate(conn, script(answer(payload)), "m", facts, episodes)
    assert note["new_facts"] == 2
    assert facts.count() == 2
    assert episodes.count() == 1
    assert pending_rows(conn) == []


def test_a_fact_that_only_repeats_what_was_recalled_is_dropped(conn):
    seed(conn)
    facts, episodes = FactStore(conn), EpisodeStore(conn)
    payload = {
        "facts": [{"subject": "alex", "content": "prefers morning meetings"}],
        "episode": "nothing new",
    }
    note = consolidate(
        conn,
        script(answer(payload)),
        "m",
        facts,
        episodes,
        recalled="- [alex] prefers morning meetings",
    )
    assert note["new_facts"] == 0
    assert facts.count() == 0


def test_failure_leaves_the_rows_pending(conn):
    seed(conn)
    facts, episodes = FactStore(conn), EpisodeStore(conn)
    assert consolidate(conn, script(), "m", facts, episodes) is None
    assert len(pending_rows(conn)) == 6


def test_a_consolidated_turn_records_the_event(settings):
    from byo.app import Agent

    gate = {
        "text": '{"needs_memory": false, "reason": "nothing to look up"}',
        "usage": {"in": 5, "out": 5},
    }
    payload = answer(
        {
            "facts": [{"subject": "alex", "content": "prefers mornings"}],
            "episode": "talked about alex",
        }
    )
    adapter = script(gate, text("noted"), payload)
    agent = Agent(settings, adapter=adapter)
    for index in range(5):
        agent.conn.execute(
            "INSERT INTO chat_log (role, content) VALUES ('user', ?)", (f"old {index}",)
        )
    agent.conn.commit()
    agent.respond("remember that alex likes mornings")
    kinds = [event["type"] for event in agent.trajectory.events]
    assert "consolidation" in kinds
    event = next(item for item in agent.trajectory.events if item["type"] == "consolidation")
    assert event["new_facts"] == 1
    assert event["kept"][0]["subject"] == "alex"


def test_unparseable_answer_keeps_rows(conn):
    seed(conn)
    facts, episodes = FactStore(conn), EpisodeStore(conn)
    assert consolidate(conn, script(text("no json here")), "m", facts, episodes) is None
    assert len(pending_rows(conn)) == 6
