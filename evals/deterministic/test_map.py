"""The map graph, its destinations and its summaries."""

from __future__ import annotations

import json

from byo.ops import map as map_ops


def write(settings, events):
    settings.trajectories_dir.mkdir(parents=True, exist_ok=True)
    path = settings.trajectories_dir / "2026-11-18.jsonl"
    path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")


def turn_events(turn_id="t_map", decision="skip", tool="list_events", tool_ok=True):
    return [
        {
            "type": "turn_start",
            "trajectory_version": 1,
            "turn_id": turn_id,
            "user_message": "what is on friday",
            "source": "dashboard",
            "session_id": "default",
            "ts": "2026-11-18T10:00:00.000+08:00",
        },
        {
            "type": "gate",
            "turn_id": turn_id,
            "decision": decision,
            "reason": "test",
            "ts": "2026-11-18T10:00:00.100+08:00",
        },
        {
            "type": "llm",
            "turn_id": turn_id,
            "iteration": 1,
            "kind": "loop",
            "model": "claude-sonnet-4-5",
            "usage": {"in": 100, "out": 20},
            "duration_ms": 900,
            "ts": "2026-11-18T10:00:01.000+08:00",
        },
        {
            "type": "tool",
            "turn_id": turn_id,
            "tool": tool,
            "args": {"start": "2026-11-20"},
            "output": "none",
            "ok": tool_ok,
            "duration_ms": 4,
            "ts": "2026-11-18T10:00:01.100+08:00",
        },
        {
            "type": "receipt",
            "turn_id": turn_id,
            "total_usd": 0.0006,
            "tokens_in": 100,
            "tokens_out": 20,
            "iterations": 1,
            "tool_calls": 1,
            "estimate": False,
            "ts": "2026-11-18T10:00:01.200+08:00",
        },
        {
            "type": "turn_end",
            "turn_id": turn_id,
            "reply": "done",
            "iterations": 1,
            "ts": "2026-11-18T10:00:01.300+08:00",
        },
    ]


def test_graph_has_the_documented_shape():
    data = map_ops.graph()
    assert data["version"] == 1
    assert len(data["groups"]) == 4
    assert len(data["nodes"]) == 13
    assert len(data["edges"]) == 15
    groups = {group["id"]: group for group in data["groups"]}
    nodes = {node["id"]: node for node in data["nodes"]}
    edges = {edge["id"]: edge for edge in data["edges"]}
    assert len(nodes) == len(data["nodes"])
    assert len(edges) == len(data["edges"])
    for node in data["nodes"]:
        assert set(node["destination"] for node in data["nodes"]) <= {
            "chat", "session", "memory", "turn", "observability"
        }
        group = groups[node["group"]]
        assert group["x"] <= node["x"] and node["x"] + node["w"] <= group["x"] + group["w"]
        assert group["y"] <= node["y"] and node["y"] + node["h"] <= group["y"] + group["h"]
        assert node["x"] >= 0 and node["x"] + node["w"] <= 1040
        assert node["y"] >= 0 and node["y"] + node["h"] <= 680
    assert all(edge["source"] in nodes and edge["target"] in nodes for edge in data["edges"])
    assert all(edge["source"] != edge["target"] for edge in data["edges"])


def test_graph_does_not_advertise_retired_or_command_line_tooling():
    data = map_ops.graph()
    text = " ".join(
        [node["id"] + " " + node["label"] for node in data["nodes"]]
        + [edge["id"] + " " + edge["label"] for edge in data["edges"]]
    ).lower()
    for word in (
        "voice", "telegram", "discord", "graph", "mcp", "skills", "hosted", "arena",
        "eval", "release",
    ):
        assert word not in text, word
    ids = {node["id"] for node in data["nodes"]}
    assert ids >= {"gate", "context", "model", "tools", "reply", "record", "cost"}
    assert ids >= {"facts", "episodes", "persona", "consolidation"}


def test_event_map_covers_the_recorded_vocabulary():
    data = map_ops.graph()
    event_map = data["event_map"]
    assert set(event_map) == {
        "turn_start", "gate", "llm", "tool", "consolidation", "receipt", "error", "turn_end"
    }
    nodes = {node["id"] for node in data["nodes"]}
    edges = {edge["id"] for edge in data["edges"]}
    for entry in event_map.values():
        assert set(entry["nodes"]) <= nodes
        assert set(entry["edges"]) <= edges
    assert set(event_map["gate"]["retrieve"]["nodes"]) == {"facts", "episodes", "persona"}
    assert set(event_map["error"]["stage_nodes"]) == {"gate", "llm", "tool", "consolidation"}
    assert set(event_map["error"]["stage_nodes"].values()) <= nodes


def test_graph_is_a_deep_copy():
    first = map_ops.graph()
    first["nodes"][0]["label"] = "mutated"
    assert map_ops.graph()["nodes"][0]["label"] != "mutated"


def test_summaries_on_an_empty_home(settings, conn):
    payload = map_ops.payload(
        settings.home, conn, settings, "7d", memory_enabled=True, tool_count=6
    )
    assert payload["turns"] == []
    assert payload["active"] is None
    assert payload["cursor"] == 0
    for node in payload["map"]["nodes"]:
        assert node["summary"]
        assert node["summary"] != "—"
    by_id = {node["id"]: node["summary"] for node in payload["map"]["nodes"]}
    assert by_id["gate"] == "no turns yet"
    assert by_id["facts"] == "0 facts"
    assert by_id["record"] == "0 turns"
    assert by_id["model"] == settings.effective_model()


def test_summaries_reflect_the_local_stores(settings, conn):
    conn.execute("INSERT INTO facts (subject, content) VALUES ('alex', 'morning')")
    conn.execute("INSERT INTO episodes (happened_at, summary) VALUES ('2026-11-18', 'met alex')")
    conn.execute(
        "INSERT INTO chat_log (role, content, session_id) VALUES ('user', 'hi', 'default')"
    )
    conn.commit()
    write(settings, turn_events(decision="skip"))
    payload = map_ops.payload(
        settings.home, conn, settings, "7d", memory_enabled=True, tool_count=6
    )
    by_id = {node["id"]: node["summary"] for node in payload["map"]["nodes"]}
    assert payload["turns"][0]["turn_id"] == "t_map"
    assert payload["turns"][0]["usd"] == 0.0006
    assert by_id["gate"] == "1 skip · 0 retrieve"
    assert by_id["facts"] == "1 fact"
    assert by_id["episodes"] == "1 episode"
    assert by_id["context"].endswith("1 message")
    assert by_id["record"] == "1 turn"
    assert by_id["observability"] == "1 tool call"
    assert by_id["cost"] == "USD 0.0006"


def test_an_unfinished_turn_is_active_with_its_events(settings, conn):
    events = [
        {
            "type": "turn_start",
            "turn_id": "t_live",
            "user_message": "still working",
            "source": "cli",
            "session_id": "default",
            "ts": "2026-11-18T10:00:00.000+08:00",
        }
    ]
    write(settings, events)
    payload = map_ops.payload(
        settings.home, conn, settings, "7d", memory_enabled=True, tool_count=6
    )
    assert payload["active"]["turn"]["turn_id"] == "t_live"
    assert payload["active"]["turn"]["state"] == "unfinished"
    assert payload["active"]["events"][0]["type"] == "turn_start"
    assert payload["cursor"] == 1
