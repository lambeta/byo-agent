"""Source and HTTP contracts for the chat live-turn lifecycle.

Mechanism: Python assertions over the static chat source plus offline stdlib HTTP turns. The
browser has no JS runner in this repository (006 D-4), so the lifetime rules are pinned where
the bug lived: the functions that own the live turn, the handoff, and the session binding.

Rejected alternative: a Node/Playwright harness. It adds a second toolchain to the default test
path for a local static page; the source contracts plus the quickstart browser scenarios cover
the same rules.
"""

from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path

from scripted import script, text, tool_call

from byo.app import Agent
from byo.loop.types import Capabilities, Refused
from byo.ops.dashboard import Dashboard, make_server

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "byo" / "ops" / "static"


def read_static(name: str) -> str:
    """Read one dashboard asset, for example js/main.js."""
    return (STATIC / name).read_text(encoding="utf-8")


def between(text: str, start: str, end: str) -> str:
    """Return the slice from start up to (not including) the next end."""
    first = text.index(start)
    last = text.index(end, first + len(start))
    return text[first:last]


def function_body(source: str, name: str) -> str:
    """Return a named classic function body by balancing its braces."""
    marker = "function " + name + "("
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unbalanced function body for {name}")

def test_foundation_new_live_binds_its_session():
    body = function_body(read_static("js/main.js"), "newLive")
    assert "function newLive(message, sessionId)" in body
    assert "session_id: sessionId" in body
    assert "has_done: false" in body
    assert "turn_id: null" in body


def test_foundation_clear_live_checks_the_turn_id():
    body = function_body(read_static("js/main.js"), "clearLive")
    assert "function clearLive(turnId)" in body
    assert "state.live.turn_id !== turnId" in body
    assert "state.live = null" in body


def test_foundation_handoff_slot_exists():
    assert "handoffTurnId: null" in read_static("js/main.js")

def test_us1_navigation_does_not_clear_the_live_turn():
    main = read_static("js/main.js")
    handler = between(
        main,
        "window.addEventListener('hashchange'",
        "\n\nrefresh().catch",
    )
    assert "state.live = null" not in handler
    assert "clearLive(" not in handler
    assert "MapLive.stop()" in handler


def test_us1_render_chat_reconciles_the_live_card():
    body = function_body(read_static("js/main.js"), "renderChat")
    assert body.count("paintLive()") >= 2
    assert body.index("paintLive()") < body.index("API.get")
    assert body.rindex("paintLive()") > body.index("history.innerHTML")


def test_us1_frames_apply_without_a_destination_gate():
    body = function_body(read_static("js/main.js"), "send")
    assert "viewName()" not in body
    assert "state.view ===" not in body
    for kind in ("gate_start", "text", "llm", "tool_start", "tool"):
        assert "kind === '" + kind + "'" in body
    assert "addItem(state.live" in body

def _post(server, path, payload):
    host, port = server.server_address
    request = urllib.request.Request(
        f"http://{host}:{port}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return response.read()


def _sse(body):
    frames = []
    for chunk in body.decode("utf-8").split("\n\n"):
        if not chunk.strip():
            continue
        event = "message"
        data = ""
        for line in chunk.splitlines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data += line[6:]
        frames.append((event, json.loads(data) if data else {}))
    return frames


class _FailingStream:
    capabilities = Capabilities(streaming=True, tool_calls=True, usage=True, tool_choice_none=True)

    def stream(self, request, on_delta=None):
        if on_delta:
            on_delta("partial ")
            on_delta("answer")
        raise Refused("provider refused")

    def complete(self, request):
        raise Refused("provider refused")


class _ExplodingStream:
    capabilities = Capabilities(streaming=True, tool_calls=True, usage=True, tool_choice_none=True)

    def stream(self, request, on_delta=None):
        raise RuntimeError("boom")

    def complete(self, request):
        raise RuntimeError("boom")


def test_us2_done_marks_the_ending_and_only_hands_off_with_has_done():
    main = read_static("js/main.js")
    done = between(main, "} else if (kind === 'done') {", "\n      }\n      paintLive();")
    assert "has_done = true" in done
    assert "payload.failed" in done
    assert "payload.limit_reached" in done
    assert "state = 'failed'" in done
    assert "payload.limit_reached ? 'limited' : 'complete'" in done
    assert "closeLive" in done
    send = function_body(main, "send")
    assert "if (!finished.has_done)" in send
    assert "state.handoffTurnId = finished.turn_id" in send


def test_us2_handoff_clears_only_after_the_transcript_is_assigned():
    body = function_body(read_static("js/main.js"), "renderChat")
    assert body.index("history.innerHTML") < body.index("clearLive(")
    assert body.index("clearLive(") < body.rindex("paintLive()")
    tail = between(body, ".catch(function () {", "});")
    assert "paintLive()" in tail
    assert "clearLive(" not in tail


def test_us2_failed_stream_keeps_partial_text(settings):
    agent = Agent(settings, adapter=_FailingStream(), memory=None)
    server = make_server(settings, agent=agent, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        frames = _sse(_post(server, "/api/chat/stream", {"message": "hello"}))
        kinds = [kind for kind, _ in frames]
        assert "text" in kinds
        assert "error" in kinds
        assert kinds[-1] == "done"
        done = [data for kind, data in frames if kind == "done"][-1]
        assert done["failed"] is True

        rows = agent.conn.execute(
            "SELECT role, content, meta FROM chat_log WHERE session_id = ? ORDER BY id",
            ("default",),
        ).fetchall()
        assistant = [dict(row) for row in rows if row["role"] == "assistant"][0]
        meta = json.loads(assistant["meta"])
        assert meta["state"] == "failed"
        assert meta["partial"] == "partial answer"
        assert "refused" in assistant["content"].lower()
    finally:
        server.shutdown()
        server.server_close()
        agent.close()


def test_us2_unexpected_exception_emits_error_without_done(settings):
    agent = Agent(settings, adapter=_ExplodingStream(), memory=None)
    server = make_server(settings, agent=agent, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        frames = _sse(_post(server, "/api/chat/stream", {"message": "hello"}))
        kinds = [kind for kind, _ in frames]
        assert "error" in kinds
        assert "done" not in kinds
        error = [data for kind, data in frames if kind == "error"][-1]
        assert error["stage"] == "turn"
    finally:
        server.shutdown()
        server.server_close()
        agent.close()


def test_us2_bubble_renders_partial_and_state():
    bubble = function_body(read_static("js/main.js"), "bubble")
    assert "message.state" in bubble
    assert "message.partial" in bubble
    assert "bubble-partial" in bubble
    assert "esc(message.partial)" in bubble
    css = read_static("style.css")
    assert ".bubble-partial" in css
    assert "white-space: pre-wrap" in css


def test_us2_live_card_marks_the_step_limit():
    card = function_body(read_static("js/render.js"), "liveCard")
    assert "'limited'" in card
    assert "step limit" in card

def test_us3_live_card_is_session_scoped():
    main = read_static("js/main.js")
    paint = function_body(main, "paintLive")
    visible = function_body(main, "liveVisible")
    assert "live.session_id" in visible
    assert "(state.viewing || state.session)" in visible
    assert "syncChatNotice()" in paint
    assert "liveVisible()" in paint
    assert "newLive(message, state.session)" in function_body(main, "send")
    picker = function_body(main, "renderSessionPicker")
    assert "state.live.session_id" in picker
    assert ".some(" in picker


def test_us3_chat_selection_and_new_chat_keep_the_turn():
    main = read_static("js/main.js")
    sessions = between(
        main,
        "document.getElementById('chat-sessions').addEventListener",
        "\n  });",
    )
    assert "state.live = null" not in sessions
    assert "clearLive(" not in sessions
    assert "paintLive()" in sessions
    new_chat = between(
        main,
        "document.getElementById('new-chat').addEventListener",
        "\n  });",
    )
    assert "state.live = null" not in new_chat
    assert "clearLive(" not in new_chat
    assert "paintLive()" in new_chat


def test_us3_notice_is_a_status_line():
    shell = read_static("index.html")
    assert 'id="chat-notice"' in shell
    assert 'role="status"' in shell
    assert 'aria-live="polite"' in shell
    css = read_static("style.css")
    assert ".chat-notice" in css
    assert ".chat-notice:empty" in css
    main = read_static("js/main.js")
    assert "function syncChatNotice()" in main
    body = function_body(main, "syncChatNotice")
    assert "notice.textContent !== text" in body


def test_us3_second_send_is_refused_without_replacing():
    body = function_body(read_static("js/main.js"), "send")
    assert "state.live.state === 'live'" in body
    assert body.index("state.live.state === 'live'") < body.index("newLive(message, state.session)")
    assert "state.handoffTurnId = null" in body
    submit = between(
        read_static("js/main.js"),
        "document.getElementById('chat-form').addEventListener('submit'",
        "\n});",
    )
    assert "state.live.state === 'live'" in submit


def test_us3_new_chat_mid_turn_keeps_the_turn(settings):
    adapter = script(text("finished"))
    agent = Agent(settings, adapter=adapter, memory=None)
    original = adapter.complete

    def complete(request):
        agent.new_session()
        return original(request)

    adapter.complete = complete
    try:
        result = agent.respond("hello")
        assert result.reply == "finished"
        rows = agent.conn.execute(
            "SELECT session_id, role, content FROM chat_log ORDER BY id"
        ).fetchall()
        assert [(row["session_id"], row["role"]) for row in rows] == [
            ("default", "user"),
            ("default", "assistant"),
        ]
        assert rows[1]["content"] == "finished"
        assert agent.session.session_id != "default"
        assert agent.session.history == []
        files = list(settings.trajectories_dir.glob("*.jsonl"))
        records = [json.loads(line) for line in files[0].read_text().splitlines()]
        assert records[0]["type"] == "turn_start"
        assert records[0]["session_id"] == "default"
    finally:
        agent.close()


def test_us3_shell_actions_keep_the_only_clear_path():
    main = read_static("js/main.js")
    assert main.count("state.live = null") == 1
    assert "state.live = null" in function_body(main, "clearLive")

    shell = between(main, "// Shell behaviors:", "// Theme toggle:")
    assert "state.live = null" not in shell
    assert "clearLive(" not in shell
    theme = between(main, "// Theme toggle:", "document.getElementById('chat-form')")
    assert "state.live = null" not in theme
    assert "clearLive(" not in theme
    assert "clearLive(" not in function_body(main, "loadTrace")
    assert "state.live = null" not in read_static("js/map.js")

def test_us2_old_history_rows_default_to_complete_and_empty_partial(settings):
    agent = Agent(settings, adapter=script(text("ok")), memory=None)
    try:
        agent.conn.execute(
            "INSERT INTO chat_log (role, content, session_id) "
            "VALUES ('assistant', 'old', 'default')"
        )
        agent.conn.commit()
        payload = Dashboard(settings, agent=agent).history("default")
        assistant = [row for row in payload["messages"] if row["role"] == "assistant"][0]
        assert assistant["state"] == "complete"
        assert assistant["partial"] == ""
        bubble = function_body(read_static("js/main.js"), "bubble")
        assert "message.state && message.state !== 'complete'" in bubble
    finally:
        agent.close()

def test_us2_limit_turn_is_marked_limited(settings):
    from byo.tools.registry import Tool

    settings.max_iterations = 1
    adapter = script(tool_call("noop", {}), text("limited reply"))
    agent = Agent(settings, adapter=adapter, memory=None)
    agent.tools.register(
        Tool("noop", "does nothing", {"type": "object", "properties": {}}, lambda: "ok")
    )
    server = make_server(settings, agent=agent, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        frames = _sse(_post(server, "/api/chat/stream", {"message": "loop"}))
        done = [data for kind, data in frames if kind == "done"][-1]
        assert done["limit_reached"] is True
        assert done["failed"] is False
        rows = agent.conn.execute(
            "SELECT meta FROM chat_log WHERE role = 'assistant' ORDER BY id"
        ).fetchall()
        meta = json.loads(rows[-1]["meta"])
        assert meta["state"] == "limited"
        assert meta["partial"] == ""
    finally:
        server.shutdown()
        server.server_close()
        agent.close()
