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
