"""The terminal timeline renders, skips bad lines and picks the newest file."""

from __future__ import annotations

import io

from rich.console import Console

from byo.ops.show_trajectory import main, newest_trajectory, render


def console() -> tuple[Console, io.StringIO]:
    buffer = io.StringIO()
    return Console(file=buffer, width=200, force_terminal=False), buffer


def test_render_prints_the_turn_and_skips_a_bad_line(settings, tmp_path):
    settings.trajectories_dir.mkdir(parents=True, exist_ok=True)
    path = settings.trajectories_dir / "2026-11-18.jsonl"
    path.write_text(
        '{"type": "turn_start", "turn_id": "t_1", "user_message": "hi", '
        '"ts": "2026-11-18T10:00:00.000+08:00"}\n'
        "not json\n"
        '{"type": "tool", "turn_id": "t_1", "tool": "list_events", "args": {}, '
        '"output": "none", "ok": true, "duration_ms": 3, "ts": "2026-11-18T10:00:01.000+08:00"}\n'
        '{"type": "turn_end", "turn_id": "t_1", "reply": "done", "iterations": 1, '
        '"ts": "2026-11-18T10:00:02.000+08:00"}\n',
        encoding="utf-8",
    )
    out, buffer = console()
    assert render(path, out) == 3
    text = buffer.getvalue()
    assert "Skipping invalid JSON on line 2." in text
    assert "turn start · hi" in text
    assert "tool · list_events" in text


def test_unknown_event_renders_generically(settings):
    settings.trajectories_dir.mkdir(parents=True, exist_ok=True)
    path = settings.trajectories_dir / "2026-11-18.jsonl"
    path.write_text(
        '{"type": "hook", "turn_id": "t_1", "ts": "2026-11-18T10:00:00.000+08:00"}\n',
        encoding="utf-8",
    )
    out, buffer = console()
    assert render(path, out) == 1
    assert "hook" in buffer.getvalue()


def test_the_reference_fixture_renders_without_skips():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    path = root / "evals" / "fixtures" / "trajectories" / "reference-sample.jsonl"
    out, buffer = console()
    count = render(path, out)
    text = buffer.getvalue()
    assert count == 7
    assert "Skipping" not in text
    for generic in ("hook", "report", "score"):
        assert generic in text


def test_main_defaults_to_the_newest_file(settings, monkeypatch, capsys):
    settings.trajectories_dir.mkdir(parents=True, exist_ok=True)
    (settings.trajectories_dir / "2026-11-17.jsonl").write_text(
        '{"type": "turn_start", "turn_id": "t_old", "user_message": "older", '
        '"ts": "2026-11-17T09:00:00.000+08:00"}\n',
        encoding="utf-8",
    )
    (settings.trajectories_dir / "2026-11-18.jsonl").write_text(
        '{"type": "turn_start", "turn_id": "t_new", "user_message": "newest", '
        '"ts": "2026-11-18T09:00:00.000+08:00"}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("BYO_HOME", str(settings.home))
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "turn start · newest" in output
    assert "turn start · older" not in output


def test_newest_file_and_missing(settings, monkeypatch):
    assert newest_trajectory(settings.home) is None
    settings.trajectories_dir.mkdir(parents=True, exist_ok=True)
    (settings.trajectories_dir / "2026-11-17.jsonl").write_text("", encoding="utf-8")
    (settings.trajectories_dir / "2026-11-18.jsonl").write_text("", encoding="utf-8")
    assert newest_trajectory(settings.home).name == "2026-11-18.jsonl"
    monkeypatch.setenv("BYO_HOME", str(settings.home))
    assert main(["does-not-exist.jsonl"]) == 1
