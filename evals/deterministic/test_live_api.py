"""The live contract: what the map polls while a turn runs."""

from __future__ import annotations

import json
import os
import threading
import urllib.request

import pytest
from scripted import script, text

from byo.app import Agent
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
        return response.status, json.loads(response.read())


def write(settings, events, name=None):
    settings.trajectories_dir.mkdir(parents=True, exist_ok=True)
    path = settings.trajectories_dir / (name or "2026-11-19.jsonl")
    path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")


def ev(type_, ts, turn="t_live", **fields):
    return {"type": type_, "turn_id": turn, "ts": ts, **fields}


def running_events(pid=None):
    return [
        ev("turn_start", "2026-11-19T10:00:00.000+08:00", source="cli", user_message="hi",
           pid=os.getpid() if pid is None else pid),
        ev("gate_start", "2026-11-19T10:00:00.100+08:00", model="small"),
        ev(
            "gate",
            "2026-11-19T10:00:00.700+08:00",
            decision="skip",
            reason="no memory",
            degraded=False,
        ),
        ev(
            "context",
            "2026-11-19T10:00:00.710+08:00",
            recalled=False,
            recalled_chars=0,
            duration_ms=1,
        ),
        ev("llm_start", "2026-11-19T10:00:00.720+08:00", iteration=1, model="big"),
    ]


def test_a_running_turn_reports_its_cues(server, settings):
    write(settings, running_events())
    status, payload = get(server, "/api/live")
    assert status == 200
    assert payload["active"] is True
    assert payload["turn"]["state"] == "running"
    assert payload["turn"]["source"] == "cli"
    assert payload["poll_ms"] == 100
    assert payload["seq"] == len(payload["cues"])
    assert payload["status"] == payload["cues"][-1]["label"]
    assert payload["cues"][-1]["states"] == {"model": "live"}
    assert payload["cues"][-1]["at"] == "2026-11-19T10:00:00.720+08:00"
    assert payload["skipped"] == 0


def test_an_empty_home_is_idle(server):
    status, payload = get(server, "/api/live")
    assert status == 200
    assert payload["turn"] is None
    assert payload["active"] is False
    assert payload["cues"] == []
    assert payload["seq"] == 0
    assert payload["status"] == "Agent idle"
    assert payload["poll_ms"] == 1000


def test_a_completed_turn_is_delivered_but_not_active(server, settings):
    events = running_events() + [
        ev("llm", "2026-11-19T10:00:03.000+08:00", iteration=1, kind="loop", model="big",
           stop_reason="end_turn", usage={"in": 1, "out": 1}, duration_ms=2280),
        ev("turn_end", "2026-11-19T10:00:03.010+08:00", reply="ok", iterations=1, state="complete"),
    ]
    write(settings, events)
    status, payload = get(server, "/api/live")
    assert status == 200
    assert payload["active"] is False
    assert payload["turn"]["state"] == "complete"
    assert payload["poll_ms"] == 1000
    assert payload["status"] == "reply"
    assert payload["cues"][-1]["states"]["record"] == "done"


def test_an_interrupted_turn_is_not_running(server, settings):
    write(settings, running_events(pid=999999))
    status, payload = get(server, "/api/live")
    assert status == 200
    assert payload["active"] is False
    assert payload["turn"]["state"] == "interrupted"
    assert payload["cues"][-1]["step"] == "synthetic"
    assert payload["cues"][-1]["states"] == {"model": "partial"}
    assert "not running" in payload["status"]
    assert payload["poll_ms"] == 1000


def test_a_record_from_before_pids_existed_is_interrupted(server, settings):
    events = running_events()
    events[0].pop("pid")
    write(settings, events)
    _, payload = get(server, "/api/live")
    assert payload["turn"]["state"] == "interrupted"


def test_the_route_is_read_only_and_never_takes_the_turn_lock(server, settings):
    write(settings, running_events())
    path = sorted(settings.trajectories_dir.glob("*.jsonl"))[0]
    before = path.read_text(encoding="utf-8")
    dash = server.dashboard
    assert dash.lock.acquire(blocking=False)
    try:
        status, _ = get(server, "/api/live")
    finally:
        dash.lock.release()
    assert status == 200
    assert path.read_text(encoding="utf-8") == before


def test_an_unknown_record_is_named_not_lit(server, settings):
    events = running_events() + [ev("future_thing", "2026-11-19T10:00:01.000+08:00", n=1)]
    write(settings, events)
    _, payload = get(server, "/api/live")
    last = payload["cues"][-1]
    assert last["states"] == {}
    assert "unmapped step" in last["label"]


def test_a_real_turn_lights_from_its_own_start(settings):
    from byo.ops.dashboard import Dashboard

    gate = {
        "text": '{"needs_memory": false, "reason": "plain hello"}',
        "usage": {"in": 5, "out": 2},
    }
    agent = Agent(settings, adapter=script(gate, text("hello")))
    agent.respond("hi there", source="dashboard")
    payload = Dashboard(settings, agent=agent).live_payload()
    assert payload["turn"]["state"] == "complete"
    assert payload["active"] is False
    starts = [cue for cue in payload["cues"] if cue["step"] == "gate_start"]
    assert starts and starts[0]["states"] == {"gate": "live"}
    model = [cue for cue in payload["cues"] if cue["step"] == "llm_start"]
    assert model and model[0]["states"] == {"model": "live"}
    # A scripted turn can finish inside one millisecond, so order is cue order,
    # not timestamp order.
    assert cue_seq(payload, "gate_start") < cue_seq(payload, "llm_start")
    assert payload["status"] == "reply"
    agent.close()


def cue_seq(payload, step):
    for cue in payload["cues"]:
        if cue["step"] == step:
            return cue["seq"]
    return -1


def test_a_busy_week_stays_within_the_poll_budget(server, settings):
    import time

    events = []
    stamp = "2026-11-19T10:{0:02d}:00.000+08:00"
    for turn in range(200):
        turn_id = "t_" + str(turn)
        events.append({"type": "turn_start", "turn_id": turn_id, "source": "cli",
                       "user_message": "hi", "pid": 999999,
                       "ts": stamp.format(turn % 60)})
        for _ in range(19):
            events.append({"type": "llm", "turn_id": turn_id, "iteration": 1, "kind": "loop",
                           "model": "big", "usage": {"in": 1, "out": 1}, "duration_ms": 10,
                           "ts": stamp.format(turn % 60)})
        events.append({"type": "turn_end", "turn_id": turn_id, "reply": "ok", "iterations": 1,
                       "state": "complete", "ts": stamp.format(turn % 60)})
    write(settings, events)
    dash = server.dashboard
    dash.live_payload()  # warm the cache
    samples = []
    for _ in range(20):
        started = time.perf_counter()
        dash.live_payload()
        samples.append((time.perf_counter() - started) * 1000)
    samples.sort()
    p95 = samples[int(len(samples) * 0.95) - 1]
    print("live p95 ms", round(p95, 2))
    assert p95 < 20, p95
    entry = next(iter(dash.feed._files.values()))
    assert entry["offset"] == entry["size"]


def test_two_viewers_can_poll_at_once(server, settings):
    write(settings, running_events())
    results = []

    def poll():
        results.append(get(server, "/api/live"))

    threads = [threading.Thread(target=poll) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert [status for status, _ in results] == [200, 200]
