"""The 200-turn / 20-step budget and exact read-model values."""

from __future__ import annotations

import json
import time

from byo.ops import map as map_ops
from byo.ops.turn_detail import detail


def write(settings, turns=200, steps=20):
    settings.trajectories_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for turn_index in range(turns):
        turn_id = f"t_scale_{turn_index:03d}"
        minute = turn_index % 60
        stamp = f"2026-11-18T10:{minute:02d}:00.000+08:00"
        records.append(
            {
                "type": "turn_start",
                "turn_id": turn_id,
                "user_message": "scale",
                "source": "dashboard",
                "session_id": "default",
                "ts": stamp,
            }
        )
        records.append(
            {
                "type": "gate",
                "turn_id": turn_id,
                "decision": "skip",
                "reason": "scale",
                "ts": stamp.replace(":00.000", ":00.100"),
            }
        )
        loops = steps // 2
        tools = steps - 1 - loops
        offset = 0
        for loop in range(loops):
            offset += 1
            records.append(
                {
                    "type": "llm",
                    "turn_id": turn_id,
                    "iteration": loop + 1,
                    "kind": "loop",
                    "model": "claude-sonnet-4-5",
                    "usage": {"in": 10, "out": 2},
                    "duration_ms": 100,
                    "ts": stamp.replace(":00.000", f":{offset:02d}.000"),
                }
            )
            if loop < tools:
                offset += 1
                records.append(
                    {
                        "type": "tool",
                        "turn_id": turn_id,
                        "tool": "list_events",
                        "args": {"start": "2026-11-20"},
                        "output": "none",
                        "ok": True,
                        "duration_ms": 1,
                        "ts": stamp.replace(":00.000", f":{offset:02d}.100"),
                    }
                )
        records.append(
            {
                "type": "receipt",
                "turn_id": turn_id,
                "total_usd": 0.0006,
                "tokens_in": 100,
                "tokens_out": 20,
                "iterations": loops,
                "tool_calls": tools,
                "estimate": False,
                "ts": stamp.replace(":00.000", ":59.000"),
            }
        )
        records.append(
            {
                "type": "turn_end",
                "turn_id": turn_id,
                "reply": "done",
                "iterations": loops,
                "ts": stamp.replace(":00.000", ":59.100"),
            }
        )
    (settings.trajectories_dir / "2026-11-18.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in records), encoding="utf-8"
    )


def test_two_hundred_turns_build_within_budget(settings, conn):
    write(settings)
    started = time.perf_counter()
    payload = map_ops.payload(
        settings.home, conn, settings, "7d", memory_enabled=True, tool_count=6
    )
    elapsed_map = time.perf_counter() - started
    assert len(payload["turns"]) == 200
    assert payload["turns"][0]["turn_id"] == "t_scale_199"
    assert payload["cursor"] > 0
    started = time.perf_counter()
    one = detail(settings.home, "t_scale_100", "7d")
    elapsed_detail = time.perf_counter() - started
    assert one is not None
    assert one["turn"]["turn_id"] == "t_scale_100"
    assert len(one["turn"]["steps"]) == 20
    assert one["hotspots"]["slowest"] is not None
    # The target is 1 s on the development laptop; keep CI-safe headroom.
    assert elapsed_map < 2.0
    assert elapsed_detail < 2.0
