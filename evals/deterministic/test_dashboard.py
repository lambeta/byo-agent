"""End to end: one turn through HTTP leaves a card, a trajectory and a waterfall."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

import pytest
from scripted import script, text, tool_call

from byo.app import Agent
from byo.ops.dashboard import make_server
from byo.ops.observability import read_events


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


def status_call(server, path, payload=None):
    """Return (status, parsed body) for a call that may legitimately fail."""
    try:
        return 200, json.loads(call(server, path, payload))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def memory_changes(settings):
    events, _ = read_events(settings.home, "all")
    return [event for event in events if event.get("type") == "memory_change"]


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
        rows = agent.conn.execute(
            "SELECT role, content FROM chat_log WHERE session_id = ? ORDER BY id",
            ("default",),
        ).fetchall()
        assert [row["content"] for row in rows] == ["go", "finished anyway"]
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


def test_tools_api_includes_the_weather_card(server):
    payload = json.loads(call(server, "/api/tools"))
    names = [tool["name"] for tool in payload["tools"]]
    assert "query_weather" in names


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


# --- spec 007: facts add and edit -----------------------------------------
#
# These drive the real handler and the real store. The view's rendering rules
# live in test_views_static.py; here the contract, status, record and mirror.


def test_memory_payload_has_counts_created_at_and_warnings(settings):
    srv = make_memory_server(settings)
    try:
        empty = json.loads(call(srv, "/api/memory"))
        assert empty["facts"] == []
        assert empty["counts"] == {"facts": 0, "episodes": 0}
        assert empty["warnings"] == []
        assert empty["mirror_path"].endswith("MEMORY.md")

        added = json.loads(
            call(
                srv,
                "/api/memory",
                {"action": "add", "subject": "tea", "content": "green over black"},
            )
        )
        assert added["ok"] is True
        assert added["fact"]["source"] == "user"
        assert added["fact"]["created_at"]
        assert added["memory"]["counts"]["facts"] == 1
        payload = json.loads(call(srv, "/api/memory"))
    finally:
        srv.shutdown()
        srv.server_close()
    assert payload["facts"][0]["created_at"] == added["fact"]["created_at"]
    assert payload["counts"]["facts"] == 1
    assert payload["warnings"] == []


def test_add_accepts_multiline_content_and_normalizes_subject(settings):
    srv = make_memory_server(settings)
    try:
        status, payload = status_call(
            srv,
            "/api/memory",
            {
                "action": "add",
                "subject": "tea\nmorning",
                "content": "line one\nline two",
            },
        )
    finally:
        srv.shutdown()
        srv.server_close()
    assert status == 200
    assert payload["fact"]["subject"] == "tea morning"
    assert payload["fact"]["content"] == "line one\nline two"


def test_add_refuses_empty_fields_with_a_field_and_records_each_attempt(settings):
    srv = make_memory_server(settings)
    try:
        first_status, first = status_call(
            srv, "/api/memory", {"action": "add", "subject": "  ", "content": "x"}
        )
        second_status, second = status_call(
            srv, "/api/memory", {"action": "add", "subject": "x", "content": "\n  "}
        )
        stored = srv.dashboard.agent.memory.facts.count()
    finally:
        srv.shutdown()
        srv.server_close()
    assert first_status == 400 and second_status == 400
    assert first["error"]["code"] == "fact_validation"
    assert first["error"]["field"] == "subject"
    assert second["error"]["field"] == "content"
    assert stored == 0
    changes = memory_changes(settings)
    assert len(changes) == 2
    assert all(change["outcome"] == "refused" for change in changes)


def test_add_limits_are_inclusive_and_enforced(settings):
    srv = make_memory_server(settings)
    try:
        accepted = json.loads(
            call(
                srv,
                "/api/memory",
                {"action": "add", "subject": "s" * 120, "content": "c" * 2000},
            )
        )
        subject_status, subject_error = status_call(
            srv,
            "/api/memory",
            {"action": "add", "subject": "s" * 121, "content": "other content"},
        )
        content_status, content_error = status_call(
            srv,
            "/api/memory",
            {"action": "add", "subject": "other subject", "content": "c" * 2001},
        )
        count = srv.dashboard.agent.memory.facts.count()
    finally:
        srv.shutdown()
        srv.server_close()
    assert accepted["fact"]["subject"] == "s" * 120
    assert accepted["fact"]["content"] == "c" * 2000
    assert subject_status == 400 and subject_error["error"]["field"] == "subject"
    assert "120" in subject_error["error"]["message"]
    assert content_status == 400 and content_error["error"]["field"] == "content"
    assert "2000" in content_error["error"]["message"]
    assert count == 1


def test_add_duplicate_is_refused_with_the_existing_fact(settings):
    srv = make_memory_server(settings)
    try:
        first = json.loads(
            call(
                srv,
                "/api/memory",
                {"action": "add", "subject": "Tea", "content": "Green  Over Black"},
            )
        )
        status, duplicate = status_call(
            srv,
            "/api/memory",
            {"action": "add", "subject": " tea ", "content": "green over\nblack"},
        )
        count = srv.dashboard.agent.memory.facts.count()
    finally:
        srv.shutdown()
        srv.server_close()
    assert status == 400
    assert duplicate["error"]["code"] == "fact_duplicate"
    assert duplicate["error"]["existing_id"] == first["fact"]["id"]
    assert count == 1


def test_edit_preserves_identity_origin_and_creation_time(settings):
    srv = make_memory_server(settings)
    try:
        added = json.loads(
            call(
                srv,
                "/api/memory",
                {"action": "add", "subject": "tea", "content": "green over black"},
            )
        )
        fact = added["fact"]
        status, edited = status_call(
            srv,
            "/api/memory",
            {
                "action": "edit",
                "id": fact["id"],
                "subject": "Tea (morning)",
                "content": fact["content"],
                "baseline_subject": fact["subject"],
                "baseline_content": fact["content"],
            },
        )
        row = dict(
            srv.dashboard.agent.conn.execute(
                "SELECT id, subject, content, source, created_at FROM facts WHERE id = ?",
                (fact["id"],),
            ).fetchone()
        )
        mirror = srv.dashboard.agent.settings.mirror_path.read_text(encoding="utf-8")
    finally:
        srv.shutdown()
        srv.server_close()
    assert status == 200
    assert edited["fact"]["id"] == fact["id"]
    assert edited["fact"]["subject"] == "Tea (morning)"
    assert row["source"] == fact["source"]
    assert row["created_at"] == fact["created_at"]
    assert "Tea (morning)" in mirror


def test_edit_with_a_stale_baseline_is_a_conflict(settings):
    srv = make_memory_server(settings)
    try:
        seed_fact(srv.dashboard.agent, "tea", "green over black")
        fact_id = srv.dashboard.agent.conn.execute(
            "SELECT id FROM facts"
        ).fetchone()[0]
        status, payload = status_call(
            srv,
            "/api/memory",
            {
                "action": "edit",
                "id": fact_id,
                "subject": "tea",
                "content": "black over green",
                "baseline_subject": "tea",
                "baseline_content": "something else",
            },
        )
        stored = srv.dashboard.agent.memory.facts.get(fact_id)
    finally:
        srv.shutdown()
        srv.server_close()
    assert status == 409
    assert payload["error"]["code"] == "fact_conflict"
    assert stored["content"] == "green over black"


def test_edit_of_a_missing_fact_is_404_and_creates_nothing(settings):
    srv = make_memory_server(settings)
    try:
        status, payload = status_call(
            srv,
            "/api/memory",
            {"action": "edit", "id": 99, "subject": "tea", "content": "black"},
        )
        count = srv.dashboard.agent.memory.facts.count()
    finally:
        srv.shutdown()
        srv.server_close()
    assert status == 404
    assert payload["error"]["code"] == "fact_not_found"
    assert count == 0


def test_edit_onto_another_fact_duplicate_is_refused(settings):
    srv = make_memory_server(settings)
    try:
        seed_fact(srv.dashboard.agent, "tea", "green over black")
        seed_fact(srv.dashboard.agent, "coffee", "black")
        rows = [
            dict(row)
            for row in srv.dashboard.agent.conn.execute(
                "SELECT id, subject, content FROM facts ORDER BY id"
            )
        ]
        status, payload = status_call(
            srv,
            "/api/memory",
            {
                "action": "edit",
                "id": rows[1]["id"],
                "subject": "tea",
                "content": "GREEN over black",
            },
        )
        stored = srv.dashboard.agent.memory.facts.get(rows[1]["id"])
    finally:
        srv.shutdown()
        srv.server_close()
    assert status == 400
    assert payload["error"]["code"] == "fact_duplicate"
    assert payload["error"]["existing_id"] == rows[0]["id"]
    assert stored["subject"] == "coffee"


def test_mirror_failure_warns_and_repairs_on_the_next_memory_read(settings, monkeypatch):
    srv = make_memory_server(settings)
    memory = srv.dashboard.agent.memory
    original = memory.rewrite_mirror
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("disk full")
        return original()

    monkeypatch.setattr(memory, "rewrite_mirror", flaky)
    try:
        status, added = status_call(
            srv,
            "/api/memory",
            {"action": "add", "subject": "tea", "content": "green over black"},
        )
        assert status == 200
        assert any(item["code"] == "mirror_write_failed" for item in added["warnings"])
        assert srv.dashboard._mirror_pending()
        assert srv.dashboard.agent.memory.facts.count() == 1

        repaired = json.loads(call(srv, "/api/memory"))
        mirror = srv.dashboard.agent.settings.mirror_path.read_text(encoding="utf-8")
    finally:
        srv.shutdown()
        srv.server_close()
    assert repaired["warnings"] == []
    assert not srv.dashboard._mirror_pending()
    assert "green over black" in mirror


def test_each_add_and_edit_attempt_records_exactly_one_event(settings):
    srv = make_memory_server(settings)
    try:
        added = json.loads(
            call(
                srv,
                "/api/memory",
                {"action": "add", "subject": "tea", "content": "green over black"},
            )
        )
        status_call(
            srv,
            "/api/memory",
            {"action": "add", "subject": "tea", "content": "green over black"},
        )
        status_call(
            srv,
            "/api/memory",
            {
                "action": "edit",
                "id": added["fact"]["id"],
                "subject": "tea",
                "content": "black over green",
                "baseline_subject": "stale",
                "baseline_content": "stale",
            },
        )
    finally:
        srv.shutdown()
        srv.server_close()
    changes = memory_changes(settings)
    assert len(changes) == 3
    assert [change["outcome"] for change in changes] == ["ok", "refused", "refused"]
    assert changes[0]["action"] == "add"
    assert changes[0]["fact_id"] == added["fact"]["id"]
    assert changes[1]["code"] == "fact_duplicate"
    assert changes[2]["code"] == "fact_conflict"
    for change in changes:
        assert "subject" not in change
        assert "content" not in change
        assert change["turn_id"] == ""
        assert change["source"] == "dashboard"


def test_events_endpoint_exposes_the_activity_record(settings):
    srv = make_memory_server(settings)
    try:
        call(
            srv,
            "/api/memory",
            {"action": "add", "subject": "tea", "content": "green over black"},
        )
        payload = json.loads(call(srv, "/api/events?cursor=0"))
    finally:
        srv.shutdown()
        srv.server_close()
    changes = [event for event in payload["events"] if event["type"] == "memory_change"]
    assert len(changes) == 1
    assert changes[0]["outcome"] == "ok"


def test_memory_view_handles_five_hundred_facts_within_the_budget(settings):
    srv = make_memory_server(settings)
    try:
        conn = srv.dashboard.agent.conn
        conn.executemany(
            "INSERT INTO facts (subject, content, source) VALUES (?, ?, 'user')",
            [(f"subject {index}", f"content number {index}") for index in range(499)],
        )
        conn.commit()

        started = time.monotonic()
        add_status, added = status_call(
            srv,
            "/api/memory",
            {"action": "add", "subject": "newest", "content": "new content"},
        )
        add_elapsed = time.monotonic() - started

        started = time.monotonic()
        payload = json.loads(call(srv, "/api/memory"))
        read_elapsed = time.monotonic() - started

        fact = added["fact"]
        started = time.monotonic()
        edit_status, edited = status_call(
            srv,
            "/api/memory",
            {
                "action": "edit",
                "id": fact["id"],
                "subject": "newest edited",
                "content": fact["content"],
                "baseline_subject": fact["subject"],
                "baseline_content": fact["content"],
            },
        )
        edit_elapsed = time.monotonic() - started
    finally:
        srv.shutdown()
        srv.server_close()
    assert add_status == 200 and edit_status == 200
    assert edited["fact"]["subject"] == "newest edited"
    assert len(payload["facts"]) == 500
    assert payload["facts"][0]["id"] == fact["id"]
    assert payload["counts"]["facts"] == 500
    assert add_elapsed < 2.0
    assert read_elapsed < 2.0
    assert edit_elapsed < 2.0


def test_data_endpoint_keeps_its_bounded_memory_slice(settings):
    srv = make_memory_server(settings)
    try:
        conn = srv.dashboard.agent.conn
        conn.executemany(
            "INSERT INTO facts (subject, content, source) VALUES (?, ?, 'user')",
            [(f"subject {index}", f"content {index}") for index in range(150)],
        )
        conn.commit()
        payload = json.loads(call(srv, "/api/data"))
    finally:
        srv.shutdown()
        srv.server_close()
    assert len(payload["memory"]["facts"]) == 100
    assert payload["memory"]["counts"]["facts"] == 100


def test_unexpected_storage_failure_is_explicit_and_recorded(settings, monkeypatch):
    srv = make_memory_server(settings)

    def boom(*args, **kwargs):
        raise RuntimeError("database is locked")

    monkeypatch.setattr("byo.ops.dashboard.curation.add", boom)
    try:
        status, payload = status_call(
            srv,
            "/api/memory",
            {"action": "add", "subject": "tea", "content": "green over black"},
        )
    finally:
        srv.shutdown()
        srv.server_close()
    assert status == 500
    assert payload["error"]["code"] == "fact_failed"
    assert "database is locked" not in payload["error"]["message"]
    changes = memory_changes(settings)
    assert len(changes) == 1
    assert changes[0]["outcome"] == "failed"
    assert changes[0]["code"] == "fact_failed"


def test_history_reads_oldest_first(settings, conn):
    from byo.ops.dashboard import Dashboard

    agent = Agent(settings, adapter=script(text("ok")), memory=None)
    conn.execute(
        "INSERT INTO chat_log (role, content, session_id) VALUES ('user', 'one', 'default')"
    )
    conn.execute(
        "INSERT INTO chat_log (role, content, session_id) VALUES ('assistant', 'two', 'default')"
    )
    conn.commit()
    payload = Dashboard(settings, agent=agent).history("default")
    assert [row["content"] for row in payload["messages"]] == ["one", "two"]
    agent.close()


def test_history_points_at_the_turn_so_a_trace_can_be_loaded(server):
    call(server, "/api/chat/stream", {"message": "book a catch-up on friday"})
    payload = json.loads(call(server, "/api/session?action=history&session_id=default"))
    assistant = [row for row in payload["messages"] if row["role"] == "assistant"]
    assert assistant, "the turn must be in the transcript"
    assert assistant[0]["turn_id"].startswith("t_")
