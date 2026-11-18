"""Wiring — build one agent from its parts. Gateways call respond().

Mechanism: settings -> database -> tools -> session -> loop, assembled once. Every
observer event is recorded in the trajectory before it reaches the surface, so the
card and the file can never disagree.

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

RECORDED = ("llm", "tool", "gate", "consolidation", "error")


AUTO = object()


class Agent:
    def __init__(
        self,
        settings: Settings | None = None,
        adapter=None,
        conn=None,
        memory=AUTO,
    ):
        self.settings = settings or load_settings()
        self.settings.ensure_home()
        self.conn = conn or connect(self.settings.home)
        self.adapter = adapter if adapter is not None else build_adapter(self.settings)
        if memory is AUTO:
            from byo.memory import Memory

            memory = Memory(self.conn, self.settings, self.adapter)
        self.memory = memory
        self.tools = build_registry(self.conn, self.settings, memory=memory)
        self.session = Session(self.settings, memory=memory)
        self.trajectory = Trajectory(self.settings)

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
        started = time.perf_counter()
        self.trajectory.start(
            message,
            source=source,
            session_id=self.session.session_id,
            model=self.settings.effective_model(),
            provider=self.settings.provider,
        )

        def observe(kind: str, event: dict) -> None:
            if kind in RECORDED:
                self.trajectory.record(kind, **event)
            if observer is not None:
                observer(kind, event)

        if self.memory is not None:
            gate = self.memory.gate(message)
            self.trajectory.record("gate", **gate)
            if observer is not None:
                observer("gate", gate)

        self.session.note_user(message)
        system = self.session.build_system(message)
        result = run_loop(
            self.adapter,
            self.settings.effective_model(),
            system,
            list(self.session.history),
            self.tools,
            max_iterations=self.settings.max_iterations,
            max_tokens=self.settings.max_tokens,
            observer=observe,
            stream=stream,
            trim=shrink,
        )
        self.session.note_assistant(result.reply)

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
        self._log(message, result, source, elapsed_ms)

        if self.memory is not None:
            note = None
            try:
                note = self.memory.maybe_consolidate(recalled=self.session.recalled)
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

        self.trajectory.end(result.reply, result.iterations)
        return result

    def _log(self, message: str, result: LoopResult, source: str, elapsed_ms: int) -> None:
        meta = json.dumps(
            {
                "turn_id": self.trajectory.turn_id,
                "iterations": result.iterations,
                "tools": [call["tool"] for call in result.tool_calls],
                "limit_reached": result.limit_reached,
                "elapsed_ms": elapsed_ms,
            }
        )
        self.conn.execute(
            "INSERT INTO chat_log (role, content, session_id, source) VALUES ('user', ?, ?, ?)",
            (message, self.session.session_id, source),
        )
        self.conn.execute(
            "INSERT INTO chat_log (role, content, session_id, source, meta) "
            "VALUES ('assistant', ?, ?, ?, ?)",
            (result.reply, self.session.session_id, source, meta),
        )
        self.conn.commit()

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.conn.close()
