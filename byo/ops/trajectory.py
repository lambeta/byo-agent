"""The trajectory sink — every turn, every step, one append-only JSON Lines file.

Mechanism: start() mints a turn id, record() adds the envelope (type, ts, turn_id),
redacts the whole record and appends one line to the local day's file. The sink is
the only writer, so redaction cannot be bypassed by a caller.

Rejected alternative: a database table. The trajectory is meant to be opened, tailed
and read by another tool; JSON Lines gives that for free and never rewrites history.
"""

from __future__ import annotations

import json
import re
import secrets
import threading
from datetime import datetime
from typing import Any

from byo.config import Settings

VERSION = 1
MAX_STRING = 20000

SENSITIVE_KEY = re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization|credential)")
VALUE_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\b[0-9a-fA-F]{32,}\b"),
)


def new_turn_id() -> str:
    return "t_" + secrets.token_hex(8)


def redact(value: Any) -> Any:
    """Field-name and value-shape redaction. Idempotent on purpose."""
    if isinstance(value, dict):
        return {
            key: ("[redacted]" if SENSITIVE_KEY.search(str(key)) else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        text = value
        for pattern in VALUE_PATTERNS:
            text = pattern.sub("[redacted]", text)
        if len(text) > MAX_STRING:
            text = text[:MAX_STRING] + "[…truncated]"
        return text
    return value


class Trajectory:
    def __init__(self, settings: Settings, clock=None) -> None:
        self.settings = settings
        self.turn_id = ""
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._lock = threading.Lock()
        self.events: list[dict[str, Any]] = []

    def now(self) -> datetime:
        return self._clock()

    def path_for(self, moment: datetime | None = None):
        moment = moment or self.now()
        return self.settings.trajectories_dir / f"{moment:%Y-%m-%d}.jsonl"

    def start(
        self,
        user_message: str,
        source: str = "cli",
        session_id: str = "default",
        model: str = "",
        provider: str = "",
    ) -> str:
        self.turn_id = new_turn_id()
        self.settings.trajectories_dir.mkdir(parents=True, exist_ok=True)
        self.record(
            "turn_start",
            trace_version=VERSION,
            trajectory_version=VERSION,
            user_message=user_message,
            source=source,
            session_id=session_id,
            model=model,
            provider=provider,
        )
        return self.turn_id

    def record(self, event_type: str, **fields: Any) -> dict[str, Any]:
        event: dict[str, Any] = {
            "type": event_type,
            "ts": self.now().isoformat(timespec="milliseconds"),
            "turn_id": self.turn_id,
        }
        event.update(fields)
        event = redact(event)
        line = json.dumps(event, ensure_ascii=False, default=str)
        self.events.append(event)
        with self._lock, self.path_for().open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return event

    def end(self, reply: str, iterations: int) -> None:
        self.record("turn_end", reply=reply, iterations=iterations)
