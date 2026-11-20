"""The local dashboard: static files, a JSON API and one SSE stream.

Mechanism: stdlib ThreadingHTTPServer. Reads are JSON; the running turn is a
Server-Sent Events stream that writes one frame per loop observer event, so a step
is on screen before the reply exists. One turn at a time, guarded by a lock.

Rejected alternative: a web framework. It would add two dependencies and a second
server model to serve nine routes a person only uses locally.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from byo.app import Agent
from byo.config import Settings, load_settings, missing_key_message
from byo.memory import curation
from byo.memory.semantic.store import FactStore
from byo.ops import feed as feed_mod
from byo.ops import highlight, observability, turn_detail
from byo.ops import map as map_ops
from byo.ops.receipt import build as build_receipt
from byo.ops.trajectory import redact

STATIC = Path(__file__).parent / "static"
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
}
MAX_BODY = 1024 * 1024
WINDOWS = ("today", "7d", "all")
FACTS_LIMIT = 500
MEMORY_STATUS = {
    "bad_request": 400,
    "fact_validation": 400,
    "fact_duplicate": 400,
    "fact_not_found": 404,
    "fact_conflict": 409,
    "fact_failed": 500,
}


def _int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _window(query: dict) -> str:
    value = (query.get("window") or ["7d"])[0]
    if value not in WINDOWS:
        raise ValueError("window must be today, 7d or all")
    return value


class Dashboard:
    def __init__(self, settings: Settings, agent: Agent | None = None) -> None:
        self.settings = settings
        self.agent = agent or Agent(settings)
        self.lock = threading.Lock()
        self.memory_lock = threading.Lock()
        self.feed = feed_mod.Feed("7d")

    # ---- payloads ---------------------------------------------------
    def data(self) -> dict:
        obs = observability.payload(
            self.settings.home, "7d", self.settings.provider, self.settings.effective_model()
        )
        conn = self.agent.conn
        facts = [
            dict(row)
            for row in conn.execute(
                "SELECT id, subject, content, source, created_at FROM facts "
                "ORDER BY id DESC LIMIT 100"
            )
        ]
        episodes = [
            dict(row)
            for row in conn.execute(
                "SELECT id, happened_at, summary FROM episodes ORDER BY id DESC LIMIT 50"
            )
        ]
        sessions = [
            dict(row)
            for row in conn.execute(
                "SELECT session_id, COUNT(*) AS messages, MAX(created_at) AS last "
                "FROM chat_log GROUP BY session_id ORDER BY last DESC"
            )
        ]
        return {
            "home": str(self.settings.home),
            "settings": self.settings_payload(),
            "turns": obs["turns"],
            "spend": obs["spend"],
            "memory": {
                "facts": facts,
                "episodes": episodes,
                "counts": {"facts": len(facts), "episodes": len(episodes)},
                "mirror_path": str(self.settings.mirror_path),
                "gate": self._gate_status(),
                "consolidation": self._consolidation_status(conn),
            },
            "sessions": sessions,
        }

    def map_payload(self, window: str) -> dict:
        return map_ops.payload(
            self.settings.home,
            self.agent.conn,
            self.settings,
            window,
            memory_enabled=self.agent.memory is not None,
            tool_count=len(self.agent.tools.names()),
            session_id=self.agent.session.session_id,
        )

    def live_payload(self) -> dict:
        """What the map polls: the newest turn's cues and whether it is live.

        The whole cue list is returned every time, so a turn that ends between two polls
        still delivers its last cues; the client diffs by seq.
        """
        events, skipped = self.feed.snapshot(self.settings.home)
        generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
        turns = observability.group_turns(events)
        if not turns:
            return {
                "generated_at": generated_at,
                "active": False,
                "turn": None,
                "seq": 0,
                "cues": [],
                "status": "Agent idle",
                "skipped": skipped,
                "poll_ms": 1000,
            }
        turn = turns[-1]
        turn_id = turn.get("turn_id")
        own = [event for event in events if event.get("turn_id") == turn_id]
        state = highlight.turn_state(own)
        units = highlight.cues(own, memory_enabled=self.agent.memory is not None)
        if state == "interrupted":
            extra = highlight.interrupted_cue(own)
            extra["seq"] = len(units)
            units.append(extra)
        active = state == "running"
        return {
            "generated_at": generated_at,
            "active": active,
            "turn": {
                "turn_id": turn_id,
                "source": turn.get("source"),
                "started_at": turn.get("started_at"),
                "ended_at": turn.get("ended_at"),
                "state": state,
            },
            "seq": len(units),
            "cues": units,
            "status": units[-1]["label"] if units else "Agent idle",
            "skipped": skipped,
            "poll_ms": 100 if active else 1000,
        }

    def tools_payload(self) -> dict:
        """The Tools view: the live registry's catalog plus recent call results.

        The catalog is the registry itself, never a copy; the results are the
        trajectory's tool events, newest first, bounded — the surface stays a
        projection of the record.
        """
        events, _skipped = self.feed.snapshot(self.settings.home)
        results = [
            {
                "tool": event.get("tool"),
                "args": event.get("args") or {},
                "output": str(event.get("output") or "")[:280],
                "ok": bool(event.get("ok")),
                "duration_ms": event.get("duration_ms"),
                "turn_id": event.get("turn_id"),
                "at": event.get("ts"),
            }
            for event in events
            if event.get("type") == "tool"
        ]
        results.reverse()
        return {"tools": self.agent.tools.schemas(), "results": results[:50]}

    def turn_payload(self, turn_id: str, window: str) -> dict | None:
        return turn_detail.detail(
            self.settings.home,
            turn_id,
            window,
            provider=self.settings.provider,
            model=self.settings.effective_model(),
        )

    def settings_payload(self) -> dict:
        return {
            "provider": self.settings.provider,
            "model": self.settings.effective_model(),
            "has_key": bool(self.settings.api_key),
            "home": str(self.settings.home),
        }

    def new_session(self) -> dict:
        return {"ok": True, "session_id": self.agent.new_session()}

    def history(self, session_id: str) -> dict:
        rows = self.agent.conn.execute(
            "SELECT role, content, source, created_at, meta FROM chat_log "
            "WHERE session_id = ? ORDER BY id LIMIT 500",
            (session_id,),
        ).fetchall()
        messages = []
        for row in rows:
            item = dict(row)
            meta = {}
            if item.get("meta"):
                try:
                    parsed = json.loads(item["meta"])
                except (TypeError, ValueError):
                    parsed = {}
                if isinstance(parsed, dict):
                    meta = parsed
            # The assistant row carries the turn id, so the chat can load that
            # turn's thinking and tool calls on demand.
            assistant = item.get("role") == "assistant"
            item["turn_id"] = str(meta.get("turn_id") or "") if assistant else ""
            item["state"] = str(meta.get("state") or "complete") if assistant else ""
            item["partial"] = str(meta.get("partial") or "") if assistant else ""
            messages.append(item)
        return {"session_id": session_id, "messages": messages}

    def memory(self, repair: bool = True) -> dict:
        """The Memory view payload: facts, episodes, counts, warnings and status.

        A pending mirror marker is repaired once before the payload is built, so a
        refresh after a mirror failure converges without rewriting files on every read.
        """
        conn = self.agent.conn
        if self._mirror_pending():
            warnings = (
                self._repair_mirror()
                if repair and self.agent.memory is not None
                else [self._mirror_warning()]
            )
        else:
            warnings = []
        facts = [
            dict(r)
            for r in conn.execute(
                "SELECT id, subject, content, source, created_at FROM facts "
                "ORDER BY id DESC LIMIT ?",
                (FACTS_LIMIT,),
            )
        ]
        episodes = [
            dict(r)
            for r in conn.execute("SELECT id, happened_at, summary FROM episodes ORDER BY id DESC")
        ]
        return {
            "facts": facts,
            "episodes": episodes,
            "counts": {"facts": len(facts), "episodes": len(episodes)},
            "mirror_path": str(self.settings.mirror_path),
            "gate": self._gate_status(),
            "consolidation": self._consolidation_status(conn),
            "warnings": warnings,
        }

    def _mirror_marker(self) -> Path:
        """A durable note that the readable mirror is behind the store."""
        return self.settings.home / ".mirror-pending"

    def _mirror_pending(self) -> bool:
        return self._mirror_marker().exists()

    @staticmethod
    def _mirror_warning() -> dict:
        return {
            "code": "mirror_write_failed",
            "message": (
                "The readable mirror is stale; it will be retried on the next Memory "
                "refresh."
            ),
        }

    def _rewrite_mirror_or_warn(self) -> list[dict]:
        """Regenerate the mirror; a failure is a warning, never a lost fact."""
        if self.agent.memory is None:
            return []
        try:
            self.agent.memory.rewrite_mirror()
        except Exception:  # noqa: BLE001 - a mirror failure must not undo the store write
            marker = self._mirror_marker()
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("mirror rewrite failed\n", encoding="utf-8")
            return [self._mirror_warning()]
        self._mirror_marker().unlink(missing_ok=True)
        return []

    def _repair_mirror(self) -> list[dict]:
        """One retry for a pending mirror; keeps the marker when it fails again."""
        try:
            self.agent.memory.rewrite_mirror()
        except Exception:  # noqa: BLE001 - keep serving the store and the warning
            return [self._mirror_warning()]
        self._mirror_marker().unlink(missing_ok=True)
        return []

    def _record_change(
        self,
        action: str,
        outcome: str,
        fact_id: int | None = None,
        code: str | None = None,
        field: str | None = None,
        warning: str | None = None,
    ) -> dict | None:
        """Append exactly one memory_change record; never fail the change for it."""
        try:
            self.agent.trajectory.record_activity(
                "memory_change",
                action=action,
                outcome=outcome,
                fact_id=fact_id,
                code=code,
                field=field,
                warning=warning,
            )
        except Exception:  # noqa: BLE001 - the fact change is already committed
            return {
                "code": "trace_write_failed",
                "message": (
                    "The change was saved, but the activity record could not be written."
                ),
            }
        return None

    @staticmethod
    def _refusal(exc: curation.Refused) -> dict:
        error: dict = {"code": exc.code, "message": exc.message}
        if exc.field:
            error["field"] = exc.field
        if exc.existing_id is not None:
            error["existing_id"] = int(exc.existing_id)
        return {"error": error}

    def _gate_status(self) -> dict:
        """Retrieve/skip counts from the recorded trajectory, plus the last call."""
        events, _skipped = self.feed.snapshot(self.settings.home)
        decisions = [event for event in events if event.get("type") == "gate"]
        last = decisions[-1] if decisions else {}
        return {
            "retrieve": sum(1 for event in decisions if event.get("decision") == "retrieve"),
            "skip": sum(1 for event in decisions if event.get("decision") == "skip"),
            "last_decision": last.get("decision"),
            "last_reason": last.get("reason"),
        }

    def _consolidation_status(self, conn) -> dict:
        from byo.memory import consolidation as consolidation_mod

        events, _skipped = self.feed.snapshot(self.settings.home)
        runs = [event for event in events if event.get("type") == "consolidation"]
        return {
            "pending": len(consolidation_mod.pending_rows(conn)),
            "threshold": self.settings.consolidate_every,
            "last_run_at": runs[-1].get("ts") if runs else None,
        }

    def memory_action(self, payload: dict) -> dict:
        """Apply one Memory-view change: explicit outcome, mirror attempt, one record."""
        action = payload.get("action")
        if action not in ("add", "edit", "forget"):
            return {
                "error": {"code": "bad_request", "message": "action must be add, edit or forget"}
            }
        if action == "forget":
            with self.memory_lock:
                self.agent.conn.execute(
                    "DELETE FROM facts WHERE id = ?", (int(payload.get("id", 0)),)
                )
                self.agent.conn.commit()
                warnings = self._rewrite_mirror_or_warn()
            return {
                "ok": True,
                "memory": self.memory(repair=False),
                "warnings": warnings,
            }
        store = (
            self.agent.memory.facts
            if self.agent.memory is not None
            else FactStore(self.agent.conn)
        )
        fact_id = _int_or_none(payload.get("id")) if action == "edit" else None
        baseline_subject = baseline_content = None
        if (
            action == "edit"
            and "baseline_subject" in payload
            and "baseline_content" in payload
        ):
            baseline_subject = str(payload.get("baseline_subject") or "")
            baseline_content = str(payload.get("baseline_content") or "")

        with self.memory_lock:
            try:
                if action == "add":
                    fact = curation.add(
                        store,
                        payload.get("subject", ""),
                        payload.get("content", ""),
                    )
                elif fact_id is None:
                    raise curation.Refused("fact_not_found", "No fact with that id.")
                else:
                    fact = curation.edit(
                        store,
                        fact_id,
                        payload.get("subject", ""),
                        payload.get("content", ""),
                        baseline_subject,
                        baseline_content,
                    )
            except curation.Refused as exc:
                self._record_change(
                    action,
                    "refused",
                    fact_id=fact_id,
                    code=exc.code,
                    field=exc.field,
                )
                return self._refusal(exc)
            except Exception:  # noqa: BLE001 - never echo storage errors or fact content
                self._record_change(action, "failed", fact_id=fact_id, code="fact_failed")
                return {
                    "error": {
                        "code": "fact_failed",
                        "message": "The fact could not be saved.",
                    }
                }
            warnings = self._rewrite_mirror_or_warn()
            trace_warning = self._record_change(
                action,
                "ok",
                fact_id=fact["id"],
                warning="mirror_write_failed" if warnings else None,
            )
            memory = self.memory(repair=False)
            if trace_warning:
                warnings = [*warnings, trace_warning]
                memory["warnings"] = [*memory.get("warnings", []), trace_warning]
            return {
                "ok": True,
                "fact": fact,
                "memory": memory,
                "warnings": warnings,
            }

    def save_settings(self, payload: dict) -> dict:
        updates = {}
        if payload.get("provider"):
            updates["BYO_PROVIDER"] = str(payload["provider"])
        if payload.get("model"):
            updates["BYO_MODEL"] = str(payload["model"])
        if payload.get("api_key"):
            updates["BYO_API_KEY"] = str(payload["api_key"])
        if updates:
            path = self.settings.dotenv_path
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
            kept = [line for line in existing if line.split("=")[0].strip() not in updates]
            kept += [f"{key}={value}" for key, value in updates.items()]
            path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        return {"ok": True, "settings": self.settings_payload()}


def _json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _error(handler: BaseHTTPRequestHandler, status: int, code: str, message: str) -> None:
    _json(handler, status, {"error": {"code": code, "message": message}})


def _body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    if length > MAX_BODY:
        raise ValueError("body too large")
    raw = handler.rfile.read(length) if length else b"{}"
    data = json.loads(raw.decode("utf-8") or "{}")
    if not isinstance(data, dict):
        raise ValueError("body must be a JSON object")
    return data


def make_handler(dash: Dashboard):
    class Handler(BaseHTTPRequestHandler):
        server_version = "byo-dashboard/0.1"
        protocol_version = "HTTP/1.0"

        def log_message(self, *args):  # keep the terminal quiet
            return

        # ---- GET ----------------------------------------------------
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path, query = parsed.path, parse_qs(parsed.query)
            try:
                if path == "/":
                    return self._static("index.html")
                if path.startswith("/static/"):
                    return self._static(unquote(path[len("/static/") :]))
                if path == "/api/data":
                    return _json(self, 200, dash.data())
                if path == "/api/observability":
                    window = _window(query)
                    return _json(
                        self,
                        200,
                        observability.payload(
                            dash.settings.home,
                            window,
                            dash.settings.provider,
                            dash.settings.effective_model(),
                        ),
                    )
                if path == "/api/map":
                    return _json(self, 200, dash.map_payload(_window(query)))
                if path == "/api/turn":
                    window = _window(query)
                    turn_id = (query.get("turn_id") or [""])[0].strip()
                    if not turn_id:
                        raise ValueError("turn_id is required")
                    payload = dash.turn_payload(turn_id, window)
                    if payload is None:
                        return _error(self, 404, "not_found", f"no turn {turn_id} in {window}")
                    return _json(self, 200, payload)
                if path == "/api/live":
                    return _json(self, 200, dash.live_payload())
                if path == "/api/events":
                    cursor = int((query.get("cursor") or ["0"])[0] or 0)
                    events, skipped = dash.feed.snapshot(dash.settings.home)
                    return _json(
                        self,
                        200,
                        {
                            "events": events[cursor:],
                            "cursor": len(events),
                            "complete": True,
                            "skipped": skipped,
                        },
                    )
                if path == "/api/session":
                    action = (query.get("action") or ["state"])[0]
                    if action == "history":
                        return _json(
                            self, 200, dash.history((query.get("session_id") or ["default"])[0])
                        )
                    return _json(
                        self,
                        200,
                        {
                            "sessions": dash.data()["sessions"],
                            "current": dash.agent.session.session_id,
                        },
                    )
                if path == "/api/tools":
                    return _json(self, 200, dash.tools_payload())
                if path == "/api/memory":
                    return _json(self, 200, dash.memory())
                if path == "/api/settings":
                    return _json(self, 200, dash.settings_payload())
                if path == "/api/health":
                    return _json(self, 200, {"ok": True, "version": "0.1.0"})
                return _error(self, 404, "not_found", f"no route for {path}")
            except ValueError as exc:
                return _error(self, 400, "bad_request", str(exc))
            except Exception as exc:  # noqa: BLE001 - a read failure must not kill the server
                return _error(self, 500, "server_error", f"{type(exc).__name__}: {exc}")

        # ---- POST ---------------------------------------------------
        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                payload = _body(self)
            except ValueError as exc:
                return _error(
                    self, 400 if "large" not in str(exc) else 413, "bad_request", str(exc)
                )
            try:
                if path == "/api/chat":
                    return self._chat(payload)
                if path == "/api/chat/stream":
                    return self._stream(payload)
                if path == "/api/memory":
                    result = dash.memory_action(payload)
                    if "error" in result:
                        status = MEMORY_STATUS.get(result["error"].get("code"), 400)
                        return _json(self, status, result)
                    return _json(self, 200, result)
                if path == "/api/settings":
                    return _json(self, 200, dash.save_settings(payload))
                if path == "/api/session":
                    if payload.get("action") == "new":
                        return _json(self, 200, dash.new_session())
                    return _error(self, 400, "bad_request", "unknown session action")
                return _error(self, 404, "not_found", f"no route for {path}")
            except ValueError as exc:
                return _error(self, 400, "bad_request", str(exc))

        # ---- pieces -------------------------------------------------
        def _static(self, relative: str) -> None:
            relative = relative or "index.html"
            if ".." in Path(relative).parts or relative.startswith("/"):
                return _error(self, 404, "not_found", "no such asset")
            target = (STATIC / relative).resolve()
            if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
                return _error(self, 404, "not_found", "no such asset")
            body = target.read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type", CONTENT_TYPES.get(target.suffix, "application/octet-stream")
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _chat(self, payload: dict) -> None:
            message = str(payload.get("message", "")).strip()
            if not message:
                return _error(self, 400, "bad_request", "message is required")
            if not dash.lock.acquire(blocking=False):
                return _error(self, 409, "conflict", "a turn is already running")
            try:
                result = dash.agent.respond(message, source="dashboard")
                return _json(
                    self,
                    200,
                    {"turn_id": dash.agent.trajectory.turn_id, "reply": result.reply},
                )
            finally:
                dash.lock.release()

        def _stream(self, payload: dict) -> None:
            message = str(payload.get("message", "")).strip()
            if not message:
                return _error(self, 400, "bad_request", "message is required")
            if not dash.lock.acquire(blocking=False):
                return _error(self, 409, "conflict", "a turn is already running")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()

            stream = {"closed": False}

            def send(kind: str, data: dict) -> None:
                """Redact before display; a gone client is a no-op, not an abort."""
                if stream["closed"]:
                    return
                body = json.dumps(redact(data), ensure_ascii=False, default=str)
                frame = f"event: {kind}\ndata: {body}\n\n"
                try:
                    self.wfile.write(frame.encode("utf-8"))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    stream["closed"] = True

            try:

                def observer(kind: str, event: dict) -> None:
                    if kind == "text":
                        send("text", event)
                    elif kind in (
                        "llm",
                        "tool",
                        "gate",
                        "consolidation",
                        "consolidation_start",
                        "error",
                        "gate_start",
                        "llm_start",
                        "tool_start",
                        "retry",
                    ):
                        # Start frames are additive: they let the dock show a step as
                        # running before its result exists, matching the map's light.
                        # A retry frame explains why a model round restarts silently.
                        send(kind, event)

                result = dash.agent.respond(
                    message, observer=observer, source="dashboard", stream=True
                )
                receipt = build_receipt(result.llm_calls, len(result.tool_calls))
                send("receipt", receipt)
                send(
                    "done",
                    {
                        "turn_id": dash.agent.trajectory.turn_id,
                        "reply": result.reply,
                        "receipt": receipt,
                        "limit_reached": result.limit_reached,
                        "failed": bool(result.error),
                    },
                )
            except BrokenPipeError:
                pass
            except Exception as exc:  # noqa: BLE001 - report a failed turn, never a fake done
                send(
                    "error",
                    {
                        "stage": "turn",
                        "error_kind": type(exc).__name__,
                        "message": f"{type(exc).__name__}: {exc}",
                    },
                )
            finally:
                dash.lock.release()

    return Handler


def make_server(settings: Settings, agent: Agent | None = None, port: int | None = None):
    dash = Dashboard(settings, agent=agent)
    server = ThreadingHTTPServer(
        ("127.0.0.1", settings.port if port is None else port), make_handler(dash)
    )
    server.daemon_threads = True
    server.dashboard = dash
    return server


def main() -> int:
    settings = load_settings()
    if not settings.api_key:
        print(missing_key_message(settings))
        return 2
    settings.ensure_home()
    try:
        server = make_server(settings)
    except OSError as exc:
        print(f"Cannot listen on 127.0.0.1:{settings.port} ({exc}). Set BYO_PORT to change it.")
        return 3
    host, port = server.server_address
    print(f"byo dashboard → http://{host}:{port}   (home: {settings.home})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
