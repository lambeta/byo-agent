"""The one-turn detail: summary, hotspots and raw records."""

from __future__ import annotations

import json
from pathlib import Path

from byo.ops.turn_detail import detail


def write(settings, events):
    settings.trajectories_dir.mkdir(parents=True, exist_ok=True)
    path = settings.trajectories_dir / "2026-11-18.jsonl"
    path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")


def events(turn_id="t_detail", receipt=True, error_stage=None):
    result = [
        {
            "type": "turn_start",
            "turn_id": turn_id,
            "user_message": "book a catch-up",
            "source": "dashboard",
            "session_id": "default",
            "ts": "2026-11-18T10:00:00.000+08:00",
        },
        {
            "type": "gate",
            "turn_id": turn_id,
            "decision": "retrieve",
            "reason": "about a person",
            "ts": "2026-11-18T10:00:00.100+08:00",
        },
        {
            "type": "llm",
            "turn_id": turn_id,
            "iteration": 1,
            "kind": "loop",
            "model": "claude-sonnet-4-5",
            "usage": {"in": 100, "out": 20},
            "duration_ms": 1840,
            "ts": "2026-11-18T10:00:02.000+08:00",
        },
        {
            "type": "tool",
            "turn_id": turn_id,
            "tool": "create_event",
            "args": {"title": "Catch-up"},
            "output": "Created event 7",
            "ok": True,
            "duration_ms": 12,
            "ts": "2026-11-18T10:00:02.100+08:00",
        },
        {
            "type": "llm",
            "turn_id": turn_id,
            "iteration": 2,
            "kind": "loop",
            "model": "claude-sonnet-4-5",
            "usage": {"in": 140, "out": 30},
            "duration_ms": 1260,
            "ts": "2026-11-18T10:00:03.500+08:00",
        },
    ]
    if error_stage:
        result.append(
            {
                "type": "error",
                "turn_id": turn_id,
                "stage": error_stage,
                "error_kind": "Refused",
                "message": "no",
                "ts": "2026-11-18T10:00:03.600+08:00",
            }
        )
    if receipt:
        result.append(
            {
                "type": "receipt",
                "turn_id": turn_id,
                "total_usd": 0.0075,
                "tokens_in": 240,
                "tokens_out": 50,
                "iterations": 2,
                "tool_calls": 1,
                "estimate": False,
                "ts": "2026-11-18T10:00:03.700+08:00",
            }
        )
    result.append(
        {
            "type": "turn_end",
            "turn_id": turn_id,
            "reply": "Booked.",
            "iterations": 2,
            "ts": "2026-11-18T10:00:03.800+08:00",
        }
    )
    return result


def test_summary_and_hotspots(settings, conn):
    write(settings, events())
    payload = detail(settings.home, "t_detail", "7d")
    assert payload["turn"]["state"] == "complete"
    expected = "question → memory retrieved → 2 model calls · 1 tool · 3.8 s · $0.0075"
    assert payload["summary"] == expected
    assert payload["hotspots"] == {"slowest": 1, "most_usd": 3}
    assert [step["kind"] for step in payload["turn"]["steps"]] == ["gate", "llm", "tool", "llm"]
    assert payload["raw"][0]["type"] == "turn_start"
    assert payload["raw"][-1]["type"] == "turn_end"
    assert payload["skipped_lines"] == 0


def test_failed_turn_summary(settings, conn):
    write(settings, events(error_stage="llm"))
    payload = detail(settings.home, "t_detail", "7d")
    assert payload["turn"]["state"] == "failed"
    assert payload["summary"].endswith("failed at llm")


def test_unfinished_turn_has_no_invented_reply_or_cost(settings, conn):
    write(settings, events(receipt=False)[:-1])
    payload = detail(settings.home, "t_detail", "7d")
    assert payload["turn"]["state"] == "unfinished"
    assert payload["turn"]["reply"] == ""
    assert payload["turn"]["receipt"] is None
    assert payload["summary"].endswith("unfinished")
    assert "cost not recorded" in payload["summary"]


def test_raw_keeps_unknown_and_text_records(settings, conn):
    records = events()
    records.insert(
        2,
        {
            "type": "text",
            "turn_id": "t_detail",
            "delta": "streamed",
            "ts": "2026-11-18T10:00:00.200+08:00",
        },
    )
    records.insert(
        3,
        {
            "type": "future_event",
            "turn_id": "t_detail",
            "value": "kept",
            "ts": "2026-11-18T10:00:00.300+08:00",
        },
    )
    write(settings, records)
    payload = detail(settings.home, "t_detail", "7d")
    assert any(record["type"] == "text" for record in payload["raw"])
    assert any(record["type"] == "future_event" for record in payload["raw"])
    assert payload["turn"]["state"] == "complete"


def test_a_turn_without_a_receipt_says_cost_not_recorded(settings, conn):
    write(settings, events(receipt=False))
    payload = detail(settings.home, "t_detail", "7d")
    assert payload["summary"].endswith("cost not recorded")


def test_zero_or_missing_duration_is_marked_not_timed(settings, conn):
    records = [
        {
            "type": "turn_start",
            "turn_id": "t_zero",
            "user_message": "hi",
            "source": "cli",
            "session_id": "default",
            "ts": "2026-11-18T10:00:00.000+08:00",
        },
        {
            "type": "gate",
            "turn_id": "t_zero",
            "decision": "skip",
            "reason": "test",
            "ts": "2026-11-18T10:00:00.000+08:00",
        },
        {
            "type": "turn_end",
            "turn_id": "t_zero",
            "reply": "hi",
            "iterations": 0,
            "ts": "2026-11-18T10:00:00.000+08:00",
        },
    ]
    write(settings, records)
    payload = detail(settings.home, "t_zero", "7d")
    assert payload["summary"].endswith("0.0 s · cost not recorded")


def test_unknown_id_returns_none(settings, conn):
    write(settings, events())
    assert detail(settings.home, "t_missing", "7d") is None


def test_pre_feature_fixture_projects_identically(settings, conn):
    fixture = (
        Path(__file__).resolve().parents[2]
        / "evals" / "fixtures" / "trajectories" / "golden-cli.jsonl"
    )
    settings.trajectories_dir.mkdir(parents=True, exist_ok=True)
    (settings.trajectories_dir / "2026-11-18.jsonl").write_text(
        fixture.read_text(), encoding="utf-8"
    )
    turn_id = "t_9f2c1d4a7b3e5c60"
    first = detail(settings.home, turn_id, "all")
    assert first is not None
    assert first["turn"]["state"] in {"complete", "failed", "unfinished"}
    assert first["raw"]
    second = detail(settings.home, turn_id, "all")
    assert first["turn"] == second["turn"]
    assert first["summary"] == second["summary"]
    assert first["hotspots"] == second["hotspots"]
