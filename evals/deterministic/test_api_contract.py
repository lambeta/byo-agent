"""The HTTP contract: routes, payloads, framing, 409 and static safety."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest
from scripted import script, text, tool_call

from byo.app import Agent
from byo.ops.dashboard import make_server


@pytest.fixture
def server(settings):
    agent = Agent(
        settings,
        adapter=script(tool_call("list_events", {"start": "2026-11-20"}), text("Nothing booked.")),
        memory=None,
    )
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


def post(server, path, payload):
    request = urllib.request.Request(
        base(server) + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return response.status, response.read()


def test_health_and_data(server):
    status, body = get(server, "/api/health")
    assert status == 200 and json.loads(body)["ok"] is True
    payload = json.loads(get(server, "/api/data")[1])
    assert set(payload) >= {"home", "settings", "turns", "memory", "spend", "sessions"}
    assert "has_key" in payload["settings"]


def test_static_shell_and_assets(server):
    status, body = get(server, "/")
    assert status == 200 and b"<title>byo" in body
    status, body = get(server, "/static/js/api.js")
    assert status == 200 and b"API" in body


def test_static_traversal_is_refused(server):
    with pytest.raises(urllib.error.HTTPError) as info:
        get(server, "/static/../dashboard.py")
    assert info.value.code == 404


def test_a_turn_through_json(server):
    status, body = post(server, "/api/chat", {"message": "what is on friday"})
    payload = json.loads(body)
    assert status == 200
    assert payload["turn_id"].startswith("t_")
    assert payload["reply"] == "Nothing booked."


def test_stream_frames_end_with_done(server):
    status, body = post(server, "/api/chat/stream", {"message": "what is on friday"})
    text_body = body.decode("utf-8")
    assert status == 200
    assert "event: tool" in text_body
    assert "event: done" in text_body
    assert text_body.index("event: tool") < text_body.index("event: done")
    done = text_body.split("event: done")[1]
    assert "Nothing booked." in done


def test_a_second_turn_conflicts(server):
    assert server.dashboard.lock.acquire(blocking=False)
    try:
        with pytest.raises(urllib.error.HTTPError) as info:
            post(server, "/api/chat", {"message": "hi"})
        assert info.value.code == 409
    finally:
        server.dashboard.lock.release()


def test_memory_routes_round_trip(server):
    status, body = post(
        server, "/api/memory", {"action": "add", "subject": "alex", "content": "morning"}
    )
    payload = json.loads(body)
    assert status == 200 and payload["ok"] is True
    fact = json.loads(get(server, "/api/memory")[1])["facts"][0]
    assert fact["subject"] == "alex"
    post(server, "/api/memory", {"action": "forget", "id": fact["id"]})
    assert json.loads(get(server, "/api/memory")[1])["facts"] == []


def test_settings_post_writes_env_and_never_echoes_the_key(server, settings):
    status, body = post(
        server, "/api/settings", {"provider": "openai", "api_key": "sk-secret-value"}
    )
    assert status == 200
    assert "sk-secret-value" not in body.decode("utf-8")
    assert "BYO_API_KEY=sk-secret-value" in (settings.home / ".env").read_text(encoding="utf-8")


def test_unknown_route_is_404(server):
    with pytest.raises(urllib.error.HTTPError) as info:
        get(server, "/api/nope")
    assert info.value.code == 404
