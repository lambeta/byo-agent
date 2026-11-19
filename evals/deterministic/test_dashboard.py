"""End to end: one turn through HTTP leaves a card, a trajectory and a waterfall."""

from __future__ import annotations

import json
import threading
import urllib.request

import pytest
from scripted import script, text, tool_call

from byo.app import Agent
from byo.ops.dashboard import make_server


@pytest.fixture
def server(settings):
    agent = Agent(
        settings,
        adapter=script(
            tool_call("create_event", {"title": "Catch-up", "start": "2026-11-20T09:00:00+08:00"}),
            text("Booked."),
        ),
        memory=None,
    )
    srv = make_server(settings, agent=agent, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def call(server, path, payload=None):
    host, port = server.server_address
    url = f"http://{host}:{port}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(request) as response:
        return response.read()


def test_a_client_disconnect_does_not_cancel_the_turn(settings):
    import socket
    import time

    from byo.tools.registry import Tool

    adapter = script(tool_call("slow", {}), text("finished anyway"))
    agent = Agent(settings, adapter=adapter, memory=None)
    agent.tools.register(
        Tool(
            "slow",
            "sleeps a moment",
            {"type": "object", "properties": {}},
            lambda: (time.sleep(0.3), "slept")[1],
        )
    )
    srv = make_server(settings, agent=agent, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, port = srv.server_address
    try:
        sock = socket.create_connection((host, port), timeout=5)
        body = json.dumps({"message": "go"}).encode("utf-8")
        head = (
            "POST /api/chat/stream HTTP/1.0\r\nHost: local\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n\r\n"
        ).encode()
        sock.sendall(head + body)
        sock.recv(256)  # the turn has started; now walk away
        sock.close()

        deadline = time.time() + 5
        written = ""
        while time.time() < deadline:
            files = list(settings.trajectories_dir.glob("*.jsonl"))
            written = "".join(path.read_text(encoding="utf-8") for path in files) if files else ""
            if '"turn_end"' in written:
                break
            time.sleep(0.05)
        assert '"turn_end"' in written, "the turn must finish after the client is gone"
        assert "finished anyway" in written
    finally:
        srv.shutdown()
        srv.server_close()


def test_card_trajectory_and_waterfall_agree(server, settings):
    call(server, "/api/chat/stream", {"message": "book a catch-up on friday"})
    data = json.loads(call(server, "/api/data"))
    assert len(data["turns"]) == 1
    turn = data["turns"][0]
    assert turn["state"] == "complete"
    kinds = [step["kind"] for step in turn["steps"]]
    assert kinds == ["llm", "tool", "llm"]
    assert turn["steps"][1]["tool"] == "create_event"
    assert turn["receipt"]["tool_calls"] == 1

    waterfall = json.loads(call(server, "/api/observability?window=7d"))
    assert waterfall["turns"][0]["turn_id"] == turn["turn_id"]
    assert waterfall["spend"]["total_usd"] == turn["receipt"]["usd"]

    files = list(settings.trajectories_dir.glob("*.jsonl"))
    assert len(files) == 1
    records = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()]
    assert records[0]["type"] == "turn_start"
    assert records[-1]["type"] == "turn_end"
    assert [r["type"] for r in records].count("receipt") == 1

def test_sessions_split_and_history_is_per_session(server):
    call(server, "/api/chat/stream", {"message": "first chat message"})
    state = json.loads(call(server, "/api/session"))
    assert state["current"] == "default"
    assert [row["session_id"] for row in state["sessions"]] == ["default"]

    created = json.loads(call(server, "/api/session", {"action": "new"}))
    assert created["ok"] is True
    assert created["session_id"] != "default"

    state = json.loads(call(server, "/api/session"))
    assert state["current"] == created["session_id"]

    call(server, "/api/chat/stream", {"message": "second chat message"})
    old = json.loads(call(server, "/api/session?action=history&session_id=default"))
    new = json.loads(
        call(server, "/api/session?action=history&session_id=" + created["session_id"])
    )
    assert [row["content"] for row in old["messages"] if row["role"] == "user"] == [
        "first chat message"
    ]
    assert [row["content"] for row in new["messages"] if row["role"] == "user"] == [
        "second chat message"
    ]


def test_unknown_session_action_is_a_400(server):
    import urllib.error

    try:
        call(server, "/api/session", {"action": "bogus"})
        raise AssertionError("expected a 400")
    except urllib.error.HTTPError as exc:
        assert exc.code == 400


def test_the_stream_marks_when_a_step_starts(server):
    body = call(server, "/api/chat/stream", {"message": "book a catch-up on friday"})
    events = [
        line[len("event: "):]
        for line in body.decode("utf-8").splitlines()
        if line.startswith("event: ")
    ]
    assert "llm_start" in events and "tool_start" in events
    assert events.index("llm_start") < events.index("llm")
    assert events.index("tool_start") < events.index("tool")
    assert events.count("llm_start") == 2
    assert events[-1] == "done"


# --- spec 006: tools and memory working in the dashboard --------------------
#
# The fixture above builds agents with memory=None. The helper below keeps the
# real Memory in the loop so the dashboard path is tested the way it runs.


def memory_agent(settings, *responses):
    """An agent wired the way the dashboard really runs: memory enabled."""
    return Agent(settings, adapter=script(*responses))  # memory defaults to AUTO


def make_memory_server(settings, *responses):
    agent = memory_agent(settings, *responses)
    srv = make_server(settings, agent=agent, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


GATE_SKIP = text('{"needs_memory": false, "reason": "no memory needed"}')
GATE_RETRIEVE = text('{"needs_memory": true, "reason": "asks about a known fact"}')


def test_tools_api_lists_the_registry_catalog(settings):
    srv = make_memory_server(settings, GATE_SKIP, text("hi"))
    try:
        payload = json.loads(call(srv, "/api/tools"))
    finally:
        srv.shutdown()
        srv.server_close()
    names = [tool["name"] for tool in payload["tools"]]
    assert names == srv.dashboard.agent.tools.names()
    for tool in payload["tools"]:
        assert tool["description"] and tool["input_schema"]["type"] == "object"


def test_tools_api_results_come_from_the_trajectory(settings):
    srv = make_memory_server(
        settings,
        GATE_SKIP,
        tool_call("list_events", {"start": "2026-11-19", "end": "2026-11-26"}),
        text("Nothing this week."),
    )
    try:
        before = json.loads(call(srv, "/api/tools"))
        assert before["results"] == []
        call(srv, "/api/chat/stream", {"message": "anything on my calendar this week?"})
        after = json.loads(call(srv, "/api/tools"))
    finally:
        srv.shutdown()
        srv.server_close()
    assert len(after["results"]) == 1
    result = after["results"][0]
    assert result["tool"] == "list_events"
    assert result["ok"] is True
    assert isinstance(result["duration_ms"], int)
    assert result["turn_id"].startswith("t_")
    assert result["output"]


def test_stream_orders_tool_frames_before_the_reply(server):
    body = call(server, "/api/chat/stream", {"message": "book a catch-up on friday"})
    events = [
        line[len("event: "):]
        for line in body.decode("utf-8").splitlines()
        if line.startswith("event: ")
    ]
    assert events.index("tool_start") < events.index("tool")
    assert events.index("tool") < events.index("done")


def seed_fact(agent, subject, content):
    agent.conn.execute(
        "INSERT INTO facts (subject, content, source) VALUES (?, ?, 'user')",
        (subject, content),
    )
    agent.conn.commit()
    agent.memory.rewrite_mirror()


def test_a_dashboard_turn_gates_and_recalls_memory(settings):
    srv = make_memory_server(settings, GATE_RETRIEVE, text("You take it black."))
    try:
        seed_fact(srv.dashboard.agent, "coffee", "takes coffee black")
        call(srv, "/api/chat/stream", {"message": "how do I take my coffee?"})
    finally:
        srv.shutdown()
        srv.server_close()
    calls = srv.dashboard.agent.adapter.calls
    assert len(calls) == 2  # gate, then the loop
    assert "takes coffee black" in calls[1].system


def test_memory_api_reports_gate_and_consolidation_status(settings):
    srv = make_memory_server(settings, GATE_RETRIEVE, text("You take it black."))
    try:
        seed_fact(srv.dashboard.agent, "coffee", "takes coffee black")
        call(srv, "/api/chat/stream", {"message": "how do I take my coffee?"})
        payload = json.loads(call(srv, "/api/memory"))
    finally:
        srv.shutdown()
        srv.server_close()
    assert payload["facts"] and payload["episodes"] == []
    gate = payload["gate"]
    assert gate["retrieve"] == 1 and gate["skip"] == 0
    assert gate["last_decision"] == "retrieve"
    consolidation = payload["consolidation"]
    assert consolidation["pending"] == 2  # the user message and the reply
    assert consolidation["threshold"] == srv.dashboard.agent.settings.consolidate_every
    assert consolidation["last_run_at"] is None


def test_memory_mutations_leave_store_payload_and_mirror_consistent(settings):
    srv = make_memory_server(settings)
    mirror = srv.dashboard.agent.settings.mirror_path
    try:
        added = json.loads(call(
            srv, "/api/memory", {"action": "add", "subject": "tea", "content": "green over black"}
        ))
        fact_id = added["memory"]["facts"][0]["id"]
        assert "green over black" in mirror.read_text(encoding="utf-8")

        edited = json.loads(call(
            srv, "/api/memory",
            {"action": "edit", "id": fact_id, "subject": "tea", "content": "black over green"}
        ))
        assert edited["memory"]["facts"][0]["content"] == "black over green"
        assert "black over green" in mirror.read_text(encoding="utf-8")
        assert "green over black" not in mirror.read_text(encoding="utf-8")

        forgotten = json.loads(call(srv, "/api/memory", {"action": "forget", "id": fact_id}))
        assert forgotten["memory"]["facts"] == []
        assert "black over green" not in mirror.read_text(encoding="utf-8")
    finally:
        srv.shutdown()
        srv.server_close()


def turn_kinds(settings, turn_id):
    files = list(settings.trajectories_dir.glob("*.jsonl"))
    records = [
        json.loads(line)
        for path in files
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    return [r["type"] for r in records if r["turn_id"] == turn_id]


def test_cli_and_dashboard_record_the_same_turn_shape(settings):
    scenario = lambda: [  # noqa: E731 - a fresh script per surface
        GATE_RETRIEVE,
        tool_call("list_events", {"start": "2026-11-19", "end": "2026-11-26"}),
        text("Nothing this week."),
    ]

    cli_agent = memory_agent(settings, *scenario())
    seed_fact(cli_agent, "coffee", "takes coffee black")
    cli_agent.respond("how do I take my coffee?", source="cli")
    cli_id = cli_agent.trajectory.turn_id
    cli_agent.close()

    srv = make_memory_server(settings, *scenario())
    try:
        seed_fact(srv.dashboard.agent, "coffee", "takes coffee black")
        call(srv, "/api/chat/stream", {"message": "how do I take my coffee?"})
        dash_id = srv.dashboard.agent.trajectory.turn_id
    finally:
        srv.shutdown()
        srv.server_close()

    assert turn_kinds(settings, cli_id) == turn_kinds(settings, dash_id)
    assert "gate" in turn_kinds(settings, cli_id)
    assert "tool" in turn_kinds(settings, cli_id)
