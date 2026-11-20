"""Wiring — build one agent from its parts. Gateways call respond().

Mechanism: settings -> database -> tools -> session -> loop, assembled once. Every
observer event is recorded in the trajectory before it reaches the surface, so the
card and the file can never disagree. A step's start is recorded too, so the file can
answer when the step was running; a turn always ends with a terminal record, even when
it raises.

Rejected alternative: letting each gateway write its own trajectory lines. Two
writers would drift, and one of them would eventually forget to redact.
"""

from __future__ import annotations

import contextlib
import json
import time

from byo.config import Settings, load_settings
from byo.db import connect
from byo.loop.adapters import build_adapter
from byo.loop.agent import LoopResult, run_loop
from byo.loop.trim import shrink
from byo.ops.receipt import build as build_receipt
from byo.ops.trajectory import Trajectory
from byo.runtime.session import Session
from byo.tools import build_registry

RECORDED = ("llm", "tool", "gate", "consolidation", "error", "llm_start", "tool_start")


AUTO = object()


class Agent:
    def __init__(
        self,
        settings: Settings | None = None,
        adapter=None,
        conn=None,
        memory=AUTO,
        weather_client=None,
        weather_clock=None,
    ):
        self.settings = settings or load_settings()
        self.settings.ensure_home()
        self.conn = conn or connect(self.settings.home)
        self.adapter = adapter if adapter is not None else build_adapter(self.settings)
        if memory is AUTO:
            from byo.memory import Memory

            memory = Memory(self.conn, self.settings, self.adapter)
        self.memory = memory
        self.tools = build_registry(
            self.conn,
            self.settings,
            memory=memory,
            weather_client=weather_client,
            weather_clock=weather_clock,
        )
        self.session = Session(self.settings, memory=memory)
        self.trajectory = Trajectory(self.settings)

    # Turn/session binding: a turn owns the Session it started in. A new chat may be
    # created while it runs; the local session keeps its history and chat_log rows in
    # the chat that sent it. Rejected alternatives: refusing new_session while the lock
    # is held, or routing a session id through every loop call.
    def respond(
        self,
        message: str,
        observer=None,
        source: str = "cli",
        stream: bool = False,
    ) -> LoopResult:
        message = (message or "").strip()
        if not message:
            return LoopResult(reply="", messages=[])
        session = self.session
        started = time.perf_counter()
        self.trajectory.start(
            message,
            source=source,
            session_id=session.session_id,
            model=self.settings.effective_model(),
            provider=self.settings.provider,
        )
        ended = False
        partial: list[str] = []

        def observe(kind: str, event: dict) -> None:
            if kind == "text":
                partial.append(str(event.get("delta") or ""))
            if kind in RECORDED:
                self.trajectory.record(kind, **event)
            if observer is not None:
                observer(kind, event)

        try:
            if self.memory is not None:
                self.trajectory.begin("gate", model=self.settings.effective_small_model())
                gate = self.memory.gate(message)
                self.trajectory.record("gate", **gate)
                if observer is not None:
                    observer("gate", gate)

            session.note_user(message)
            assembled = time.perf_counter()
            system = session.build_system(message)
            recalled = session.recalled or ""
            self.trajectory.record(
                "context",
                recalled=bool(recalled),
                recalled_chars=len(recalled),
                duration_ms=int((time.perf_counter() - assembled) * 1000),
            )

            result = run_loop(
                self.adapter,
                self.settings.effective_model(),
                system,
                list(session.history),
                self.tools,
                max_iterations=self.settings.max_iterations,
                max_tokens=self.settings.max_tokens,
                observer=observe,
                stream=stream,
                trim=shrink,
            )
            session.note_assistant(result.reply)

            receipt = build_receipt(result.llm_calls, len(result.tool_calls))
            self.trajectory.record(
                "receipt",
                total_usd=receipt["usd"],
                tokens_in=receipt["tokens_in"],
                tokens_out=receipt["tokens_out"],
                iterations=receipt["iterations"],
                tool_calls=receipt["tool_calls"],
                estimate=receipt["estimate"],
            )

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            self._log(message, result, source, elapsed_ms, "".join(partial), session.session_id)

            if self.memory is not None:
                note = None
                try:
                    note = self.memory.maybe_consolidate(
                        recalled=session.recalled,
                        on_start=lambda pending: self.trajectory.begin(
                            "consolidation", pending=pending
                        ),
                    )
                except Exception as exc:  # noqa: BLE001 - consolidation never fails a turn
                    failure = {
                        "stage": "consolidation",
                        "error_kind": "Internal",
                        "message": f"{type(exc).__name__}: {exc}",
                    }
                    self.trajectory.record("error", **failure)
                    if observer is not None:
                        observer("error", failure)
                if note:
                    self.trajectory.record("consolidation", **note)
                    if observer is not None:
                        observer("consolidation", note)

            state = "complete"
            if result.error:
                state = "failed"
            elif result.limit_reached:
                state = "limited"
            self.trajectory.end(result.reply, result.iterations, state=state)
            ended = True
            return result
        except BaseException as exc:
            if not ended:
                failure = {
                    "stage": "turn",
                    "error_kind": type(exc).__name__,
                    "message": f"{type(exc).__name__}: {exc}",
                }
                self.trajectory.record("error", **failure)
                self.trajectory.end("", 0, state="failed")
            raise

    def _log(
        self,
        message: str,
        result: LoopResult,
        source: str,
        elapsed_ms: int,
        partial: str = "",
        session_id: str = "default",
    ) -> None:
        state = "failed" if result.error else ("limited" if result.limit_reached else "complete")
        meta = json.dumps(
            {
                "turn_id": self.trajectory.turn_id,
                "iterations": result.iterations,
                "tools": [call["tool"] for call in result.tool_calls],
                "limit_reached": result.limit_reached,
                "elapsed_ms": elapsed_ms,
                "state": state,
                "partial": partial[:4000] if result.error else "",
            }
        )
        self.conn.execute(
            "INSERT INTO chat_log (role, content, session_id, source) VALUES ('user', ?, ?, ?)",
            (message, session_id, source),
        )
        self.conn.execute(
            "INSERT INTO chat_log (role, content, session_id, source, meta) "
            "VALUES ('assistant', ?, ?, ?, ?)",
            (result.reply, session_id, source, meta),
        )
        self.conn.commit()

    def new_session(self) -> str:
        """Start a fresh chat session: new id, empty working history.

        Past sessions stay in chat_log; only the in-memory working set resets.
        """
        session_id = "s-" + time.strftime("%Y%m%d-%H%M%S")
        self.session = Session(self.settings, memory=self.memory, session_id=session_id)
        return session_id

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.conn.close()
