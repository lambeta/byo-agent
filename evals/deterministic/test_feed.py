"""The cached feed must equal a full read, and read only new bytes."""

from __future__ import annotations

import json
import os
from datetime import date

from byo.ops.feed import Feed
from byo.ops.observability import read_events


def write_day(settings, day, events, mode="w"):
    settings.trajectories_dir.mkdir(parents=True, exist_ok=True)
    path = settings.trajectories_dir / f"{day}.jsonl"
    with path.open(mode, encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")
    return path


def event(kind, turn="t_1", **fields):
    return {"type": kind, "turn_id": turn, "ts": "2026-11-19T10:00:00.000+08:00", **fields}


def test_incremental_equals_full_after_each_append(settings):
    feed = Feed("7d")
    today = date.today().isoformat()
    path = write_day(settings, today, [event("turn_start")])
    assert feed.snapshot(settings.home)[0] == read_events(settings.home, "7d")[0]
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event("llm")) + "\n")
    assert feed.snapshot(settings.home)[0] == read_events(settings.home, "7d")[0]
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event("turn_end")) + "\n")
    events, skipped = feed.snapshot(settings.home)
    assert events == read_events(settings.home, "7d")[0]
    assert skipped == 0


def test_a_partial_line_is_not_consumed_until_it_is_complete(settings):
    feed = Feed("7d")
    today = date.today().isoformat()
    path = write_day(settings, today, [event("turn_start")])
    feed.snapshot(settings.home)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"type": "llm"')
    assert feed.snapshot(settings.home)[0] == read_events(settings.home, "7d")[0]
    with path.open("a", encoding="utf-8") as handle:
        handle.write(', "turn_id": "t_1"}' + "\n")
    assert feed.snapshot(settings.home)[0] == read_events(settings.home, "7d")[0]


def test_truncation_and_replacement_force_a_reload(settings):
    feed = Feed("7d")
    today = date.today().isoformat()
    path = write_day(settings, today, [event("turn_start"), event("llm")])
    assert len(feed.snapshot(settings.home)[0]) == 2
    path.write_text(json.dumps(event("turn_start")) + "\n", encoding="utf-8")
    assert feed.snapshot(settings.home)[0] == read_events(settings.home, "7d")[0]
    path.write_text(
        json.dumps(event("turn_start")) + "\n" + json.dumps(event("tool")) + "\n",
        encoding="utf-8",
    )
    assert feed.snapshot(settings.home)[0] == read_events(settings.home, "7d")[0]


def test_a_new_day_file_joins_the_window(settings):
    feed = Feed("7d")
    today = date.today().isoformat()
    write_day(settings, today, [event("turn_start")])
    feed.snapshot(settings.home)
    write_day(settings, today, [event("llm")], mode="a")
    write_day(settings, "2026-11-18", [event("turn_start", turn="t_2")])
    assert feed.snapshot(settings.home)[0] == read_events(settings.home, "7d")[0]


def test_bad_lines_are_counted_not_fatal(settings):
    feed = Feed("7d")
    today = date.today().isoformat()
    path = write_day(settings, today, [event("turn_start")])
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{not json}\n")
        handle.write(json.dumps(event("llm")) + "\n")
    events, skipped = feed.snapshot(settings.home)
    assert skipped == 1
    assert [item["type"] for item in events] == ["turn_start", "llm"]
    assert (events, skipped) == read_events(settings.home, "7d")


def test_windows_match_the_full_read(settings):
    write_day(settings, "2026-11-18", [event("turn_start", turn="t_old")])
    today = date.today().isoformat()
    write_day(settings, today, [event("turn_start", turn="t_new")])
    for window in ("today", "7d", "all"):
        cached = Feed(window).snapshot(settings.home)[0]
        assert cached == read_events(settings.home, window)[0], window


def test_an_atomic_rename_replacement_forces_a_reload(settings):
    """temp-file + rename swaps the inode; the cached offset must not survive it."""
    feed = Feed("7d")
    today = date.today().isoformat()
    path = write_day(settings, today, [event("turn_start"), event("llm")])
    assert len(feed.snapshot(settings.home)[0]) == 2
    replacement = settings.trajectories_dir / ".pending"
    for turn in ("t_2", "t_3"):  # larger and smaller replacements both reload
        with replacement.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(event("turn_start", turn=turn)) + "\n")
            if turn == "t_2":
                handle.write(json.dumps(event("llm", turn=turn)) + "\n")
                handle.write(json.dumps(event("turn_end", turn=turn)) + "\n")
        replacement.replace(path)
        events, _ = feed.snapshot(settings.home)
        assert events == read_events(settings.home, "7d")[0]
        assert {item["turn_id"] for item in events} == {turn}


def test_an_mtime_only_change_forces_a_reload(settings):
    feed = Feed("7d")
    today = date.today().isoformat()
    path = write_day(settings, today, [event("turn_start")])
    first, _ = feed.snapshot(settings.home)
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    again, _ = feed.snapshot(settings.home)
    assert again == first == read_events(settings.home, "7d")[0]


def test_an_unknown_window_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="window"):
        Feed("month")


def test_a_missing_directory_reads_as_empty(settings):
    feed = Feed("7d")
    assert feed.snapshot(settings.home) == ([], 0)
    write_day(settings, date.today().isoformat(), [event("turn_start")])
    events, skipped = feed.snapshot(settings.home)
    assert len(events) == 1
    assert skipped == 0


def test_a_non_object_json_line_is_counted_not_served(settings):
    feed = Feed("7d")
    today = date.today().isoformat()
    path = write_day(settings, today, [event("turn_start")])
    with path.open("a", encoding="utf-8") as handle:
        handle.write("[1, 2]\n")
        handle.write(json.dumps(event("llm")) + "\n")
    events, skipped = feed.snapshot(settings.home)
    assert skipped == 1
    assert [item["type"] for item in events] == ["turn_start", "llm"]


def test_a_deleted_day_file_is_evicted_from_the_cache(settings):
    feed = Feed("all")
    today = date.today().isoformat()
    path = write_day(settings, today, [event("turn_start")])
    assert len(feed.snapshot(settings.home)[0]) == 1
    path.unlink()
    assert feed.snapshot(settings.home) == ([], 0)
    write_day(settings, today, [event("turn_start", turn="t_2")])
    events, _ = feed.snapshot(settings.home)
    assert [item["turn_id"] for item in events] == ["t_2"]
