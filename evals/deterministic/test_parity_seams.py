"""The parity seams, checked mechanically (SC-006)."""

from __future__ import annotations

from pathlib import Path

from scripted import script, text, tool_call

from byo import __version__
from byo.app import Agent
from byo.config import load_settings
from byo.ops import observability

ROOT = Path(__file__).resolve().parents[2]


def test_commands_keep_the_reference_shape(capsys):
    from byo.__main__ import USAGE

    for verb in ("dashboard", "trajectory"):
        assert verb in USAGE
    from byo.__main__ import main

    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_default_address_matches(settings):
    assert settings.port == 7777
    assert load_settings(env={}).home.name == ".byo"


def test_home_layout_matches(settings):
    from byo.db import connect

    settings.ensure_home()
    connect(settings.home).close()
    assert settings.trajectories_dir.is_dir()
    assert settings.outbox_dir.is_dir()
    assert settings.memory_dir.is_dir()
    assert settings.db_path.exists()


def test_trajectory_vocabulary(settings):
    agent = Agent(
        settings,
        adapter=script(tool_call("list_events", {"start": "2026-11-20"}), text("none")),
        memory=None,
    )
    agent.respond("what is on friday")
    kinds = [event["type"] for event in agent.trajectory.events]
    assert kinds[0] == "turn_start" and kinds[-1] == "turn_end"
    assert set(kinds) <= {
        "turn_start",
        "gate",
        "llm",
        "tool",
        "consolidation",
        "receipt",
        "error",
        "turn_end",
    }
    agent.close()


def test_card_payload_keys(settings):
    agent = Agent(settings, adapter=script(text("hello")), memory=None)
    agent.respond("hi")
    events, _ = observability.read_events(settings.home)
    turn = observability.build_turn(observability.group_turns(events)[0])
    assert set(turn) >= {
        "turn_id",
        "source",
        "session_id",
        "user_message",
        "started_at",
        "state",
        "iterations",
        "reply",
        "gate",
        "steps",
        "receipt",
    }
    agent.close()


def test_fixtures_render_in_this_timeline():
    import io

    from rich.console import Console

    from byo.ops.show_trajectory import render

    fixtures = ROOT / "evals" / "fixtures" / "trajectories"
    assert (fixtures / "golden-cli.jsonl").is_file()
    buffer = io.StringIO()
    count = render(fixtures / "golden-cli.jsonl", Console(file=buffer, width=200))
    assert count == 7
    assert "turn start · book a catch-up" in buffer.getvalue()
