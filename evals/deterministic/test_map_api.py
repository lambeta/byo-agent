"""The map, turn and feed HTTP contracts."""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from scripted import script, text

from byo.app import Agent
from byo.ops import observability
from byo.ops.dashboard import make_server


@pytest.fixture
def server(settings):
    agent = Agent(settings, adapter=script(text("ok")), memory=None)
    srv = make_server(settings, agent=agent, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def base(server) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}"


def get(server, path):
    with urllib.request.urlopen(base(server) + path) as response:
        return response.status, response.read()


def write(settings, events, name="2026-11-18.jsonl"):
    settings.trajectories_dir.mkdir(parents=True, exist_ok=True)
    (settings.trajectories_dir / name).write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )


def turn_events(turn_id, start="10:00", decision="skip", tool_ok=True):
    stamp = f"2026-11-18T{start}:00.000+08:00"
    return [
        {
            "type": "turn_start",
            "trajectory_version": 1,
            "turn_id": turn_id,
            "user_message": "what is on friday",
            "source": "dashboard",
            "session_id": "default",
            "ts": stamp,
        },
        {
            "type": "gate",
            "turn_id": turn_id,
            "decision": decision,
            "reason": "test",
            "ts": stamp.replace(":00.000", ":00.100"),
        },
        {
            "type": "llm",
            "turn_id": turn_id,
            "iteration": 1,
            "kind": "loop",
            "model": "claude-sonnet-4-5",
            "usage": {"in": 100, "out": 20},
            "duration_ms": 900,
            "ts": stamp.replace(":00.000", ":01.000"),
        },
        {
            "type": "tool",
            "turn_id": turn_id,
            "tool": "list_events",
            "args": {"start": "2026-11-20"},
            "output": "none",
            "ok": tool_ok,
            "duration_ms": 4,
            "ts": stamp.replace(":00.000", ":01.100"),
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
            "ts": stamp.replace(":00.000", ":01.200"),
        },
        {
            "type": "turn_end",
            "turn_id": turn_id,
            "reply": "done",
            "iterations": 1,
            "ts": stamp.replace(":00.000", ":01.300"),
        },
    ]


def test_map_payload_contract(server):
    status, body = get(server, "/api/map?window=7d")
    payload = json.loads(body)
    assert status == 200
    assert set(payload) == {
        "window", "generated_at", "map", "turns", "active", "cursor", "skipped_lines"
    }
    assert payload["window"] == "7d"
    assert len(payload["map"]["nodes"]) == 13
    assert len(payload["map"]["edges"]) == 15
    nodes = {node["id"] for node in payload["map"]["nodes"]}
    assert nodes >= {"gate", "model", "tools", "reply", "record"}
    assert all(node["summary"] for node in payload["map"]["nodes"])
    assert payload["turns"] == []
    assert payload["active"] is None
    assert payload["cursor"] == 0
    assert payload["skipped_lines"] == 0
    assert set(payload["map"]["event_map"]) == {
        "turn_start",
        "gate_start",
        "gate",
        "context",
        "llm_start",
        "llm",
        "retry",
        "tool_start",
        "tool",
        "consolidation_start",
        "consolidation",
        "receipt",
        "error",
        "turn_end",
    }


def test_map_rejects_a_bad_window(server):
    with pytest.raises(urllib.error.HTTPError) as info:
        get(server, "/api/map?window=year")
    assert info.value.code == 400


def test_map_turns_are_newest_first(server, settings):
    write(settings, turn_events("t_first", "10:00") + turn_events("t_second", "11:00"))
    payload = json.loads(get(server, "/api/map?window=all")[1])
    assert [turn["turn_id"] for turn in payload["turns"]] == ["t_second", "t_first"]
    assert set(payload["turns"][0]) >= {
        "turn_id", "started_at", "ended_at", "source", "state",
        "iterations", "tool_calls", "usd", "estimate"
    }


def test_map_active_and_cursor(server, settings):
    write(
        settings,
        [
            {
                "type": "turn_start",
                "turn_id": "t_live",
                "user_message": "still working",
                "source": "cli",
                "session_id": "default",
                "ts": "2026-11-18T10:00:00.000+08:00",
                "pid": os.getpid(),
            }
        ],
    )
    payload = json.loads(get(server, "/api/map?window=7d")[1])
    assert payload["active"]["turn"]["turn_id"] == "t_live"
    assert payload["active"]["turn"]["state"] == "unfinished"
    assert payload["active"]["events"][0]["type"] == "turn_start"
    assert payload["cursor"] == 1
    feed = json.loads(get(server, f"/api/events?cursor={payload['cursor']}")[1])
    assert feed["events"] == []
    assert feed["cursor"] == 1
    assert feed["skipped"] == 0


def test_an_unfinished_turn_with_a_dead_writer_is_not_active(server, settings):
    write(
        settings,
        [
            {
                "type": "turn_start",
                "turn_id": "t_dead",
                "user_message": "died",
                "source": "cli",
                "session_id": "default",
                "ts": "2026-11-18T10:00:00.000+08:00",
                "pid": 999999,
            }
        ],
    )
    payload = json.loads(get(server, "/api/map?window=7d")[1])
    assert payload["active"] is None
    assert payload["turns"][0]["state"] == "unfinished"


def test_a_record_from_before_pids_existed_is_never_active(server, settings):
    write(
        settings,
        [
            {
                "type": "turn_start",
                "turn_id": "t_legacy",
                "user_message": "old",
                "source": "cli",
                "session_id": "default",
                "ts": "2026-11-18T10:00:00.000+08:00",
            }
        ],
    )
    payload = json.loads(get(server, "/api/map?window=7d")[1])
    assert payload["active"] is None


def test_turn_detail_route(server, settings):
    write(settings, turn_events("t_detail"))
    status, body = get(server, "/api/turn?turn_id=t_detail&window=7d")
    payload = json.loads(body)
    assert status == 200
    assert set(payload) == {"window", "turn", "summary", "hotspots", "raw", "skipped_lines"}
    assert payload["turn"]["state"] == "complete"
    assert payload["summary"].startswith("question → memory skipped")
    assert payload["hotspots"] == {"slowest": 1, "most_usd": 1}
    assert payload["raw"][0]["type"] == "turn_start"
    assert payload["raw"][-1]["type"] == "turn_end"
    assert payload["skipped_lines"] == 0

    with pytest.raises(urllib.error.HTTPError) as missing:
        get(server, "/api/turn?window=7d")
    assert missing.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as unknown:
        get(server, "/api/turn?turn_id=t_nope&window=7d")
    assert unknown.value.code == 404
    with pytest.raises(urllib.error.HTTPError) as bad:
        get(server, "/api/turn?turn_id=t_detail&window=year")
    assert bad.value.code == 400


def test_feed_reports_skipped_lines_and_does_not_need_the_lock(server, settings):
    write(settings, turn_events("t_feed"))
    path = settings.trajectories_dir / "2026-11-18.jsonl"
    path.write_text(path.read_text(encoding="utf-8") + "{not json}\n", encoding="utf-8")
    with server.dashboard.lock:
        status, body = get(server, "/api/events?cursor=0")
        assert status == 200
        feed = json.loads(body)
        assert len(feed["events"]) == 6
        assert feed["skipped"] == 1
        assert feed["cursor"] == 6
        assert json.loads(get(server, "/api/map?window=all")[1])["turns"][0]["turn_id"] == "t_feed"
        detail_body = json.loads(get(server, "/api/turn?turn_id=t_feed&window=all")[1])
        assert detail_body["turn"]["state"] == "complete"


def test_pre_feature_fixture_keeps_the_same_projection(server, settings):
    fixture = (
        Path(__file__).resolve().parents[2]
        / "evals" / "fixtures" / "trajectories" / "golden-cli.jsonl"
    )
    (settings.trajectories_dir / "2026-11-18.jsonl").write_text(
        fixture.read_text(encoding="utf-8"), encoding="utf-8"
    )
    events, _ = observability.read_events(settings.home, "all")
    expected = observability.build_turn(observability.group_turns(events)[0])
    payload = json.loads(get(server, "/api/turn?turn_id=t_9f2c1d4a7b3e5c60&window=all")[1])
    assert payload["turn"] == expected
    assert [step["kind"] for step in payload["turn"]["steps"]] == [
        step["kind"] for step in expected["steps"]
    ]
    assert [step.get("duration_ms") for step in payload["turn"]["steps"]] == [
        step.get("duration_ms") for step in expected["steps"]
    ]
    map_payload = json.loads(get(server, "/api/map?window=all")[1])
    assert map_payload["turns"][0]["turn_id"] == "t_9f2c1d4a7b3e5c60"
    assert map_payload["turns"][0]["usd"] == expected["receipt"]["usd"]


def test_fifty_turns_agree_across_card_map_and_detail(server, settings):
    records = []
    for index in range(50):
        records.extend(turn_events(f"t_fifty_{index:02d}", f"10:{index:02d}"))
    write(settings, records)
    data = json.loads(get(server, "/api/data")[1])
    assert len(data["turns"]) == 50
    card = next(turn for turn in data["turns"] if turn["turn_id"] == "t_fifty_17")
    map_payload = json.loads(get(server, "/api/map?window=all")[1])
    listed = next(turn for turn in map_payload["turns"] if turn["turn_id"] == "t_fifty_17")
    detail_payload = json.loads(get(server, "/api/turn?turn_id=t_fifty_17&window=all")[1])
    assert card["iterations"] == listed["iterations"] == detail_payload["turn"]["iterations"]
    assert card["receipt"]["usd"] == listed["usd"] == detail_payload["turn"]["receipt"]["usd"]
    assert [step["kind"] for step in card["steps"]] == [
        step["kind"] for step in detail_payload["turn"]["steps"]
    ]
    assert [step.get("duration_ms") for step in card["steps"]] == [
        step.get("duration_ms") for step in detail_payload["turn"]["steps"]
    ]
    assert listed["tool_calls"] == card["receipt"]["tool_calls"]
