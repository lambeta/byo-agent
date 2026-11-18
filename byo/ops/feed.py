"""The incremental feed reader the live view polls.

Mechanism: cache every day file's byte offset, size, mtime and parsed records; a poll
reads only the bytes appended since the previous one. A truncated, replaced or new file
is reloaded in full. The window rule is the same one observability.read_events uses, and
the merged list is built per call from the cached records, so the cost of a poll is the
number of files plus the new bytes, never the size of the window.

Rejected alternative: re-reading and re-parsing the whole window on every poll. The live
player polls ten times a second while a turn runs, and a busy week is megabytes of JSON.
"""

from __future__ import annotations

import json
import threading
from datetime import date, timedelta
from pathlib import Path
from typing import Any

WINDOWS = ("today", "7d", "all")


class Feed:
    """One cached, append-only reader per window."""

    def __init__(self, window: str = "7d") -> None:
        if window not in WINDOWS:
            raise ValueError("window must be today, 7d or all")
        self.window = window
        self._files: dict[Path, dict[str, Any]] = {}
        self._lock = threading.Lock()

    # ---- public -----------------------------------------------------
    def snapshot(self, home: Path) -> tuple[list[dict[str, Any]], int]:
        """The window's events in file order, plus the malformed-line count."""
        directory = Path(home) / "trajectories"
        with self._lock:
            if not directory.is_dir():
                self._files.clear()
                return [], 0
            selected = self._selected(directory)
            events: list[dict[str, Any]] = []
            skipped = 0
            for path in selected:
                entry = self._refresh(path)
                events.extend(entry["events"])
                skipped += entry["skipped"]
            keep = set(selected)
            for path in list(self._files):
                if path not in keep:
                    del self._files[path]
            return list(events), skipped

    # ---- internals --------------------------------------------------
    def _selected(self, directory: Path) -> list[Path]:
        files = sorted(directory.glob("*.jsonl"))
        if self.window == "today":
            return files[-1:]
        if self.window == "7d":
            floor = (date.today() - timedelta(days=6)).isoformat()
            return [path for path in files if path.stem >= floor]
        return files

    def _refresh(self, path: Path) -> dict[str, Any]:
        try:
            stat = path.stat()
        except OSError:
            return {"size": 0, "mtime_ns": 0, "offset": 0, "events": [], "skipped": 0}
        entry = self._files.get(path)
        if entry is None or stat.st_size < entry["size"] or stat.st_mtime_ns < entry["mtime_ns"]:
            entry = self._reload(path, stat)
            self._files[path] = entry
            return entry
        if stat.st_size > entry["size"]:
            self._extend(path, entry, stat)
            return entry
        if stat.st_mtime_ns != entry["mtime_ns"]:
            entry = self._reload(path, stat)
            self._files[path] = entry
        return entry

    def _reload(self, path: Path, stat) -> dict[str, Any]:
        try:
            data = path.read_bytes()
        except OSError:
            data = b""
        events, skipped, consumed = self._parse(data)
        return {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "offset": consumed,
            "events": events,
            "skipped": skipped,
        }

    def _extend(self, path: Path, entry: dict[str, Any], stat) -> None:
        try:
            with path.open("rb") as handle:
                handle.seek(entry["offset"])
                data = handle.read()
        except OSError:
            data = b""
        events, skipped, consumed = self._parse(data)
        entry["events"].extend(events)
        entry["skipped"] += skipped
        entry["offset"] += consumed
        entry["size"] = stat.st_size
        entry["mtime_ns"] = stat.st_mtime_ns

    def _parse(self, data: bytes) -> tuple[list[dict[str, Any]], int, int]:
        """(events, skipped, bytes consumed). A trailing partial line is left unread."""
        end = data.rfind(b"\n")
        consumed = end + 1
        events: list[dict[str, Any]] = []
        skipped = 0
        for line in data[:consumed].split(b"\n"):
            if not line.strip():
                continue
            try:
                event = json.loads(line.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                skipped += 1
                continue
            if isinstance(event, dict):
                events.append(event)
            else:
                skipped += 1
        return events, skipped, consumed
