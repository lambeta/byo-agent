"""The terminal surface: exit codes, the missing-key path, and step ordering."""

from __future__ import annotations

from scripted import error, script, text, tool_call

from byo.config import load_settings
from byo.gateway.cli import main


def test_missing_key_exits_two_with_one_actionable_line(home, capsys):
    settings = load_settings(env={}, home=home)
    assert main(settings=settings, reader=lambda prompt: "") == 2
    out = "".join(capsys.readouterr().out.split())
    assert "BYO_API_KEY" in out
    assert "".join(str(home / ".env").split()) in out


def test_unknown_flag_exits_one(capsys):
    from byo.__main__ import main as entry

    assert entry(["nope"]) == 1
    assert "unknown command" in capsys.readouterr().err


def test_version_and_help(capsys):
    from byo.__main__ import main as entry

    assert entry(["--version"]) == 0
    assert entry(["--help"]) == 0
    out = capsys.readouterr().out
    assert "byo" in out


def test_memory_command_shows_facts_and_pending(home, capsys):
    from byo.app import Agent

    settings = load_settings(env={}, home=home)
    settings.ensure_home()
    agent = Agent(settings, adapter=script(), memory=None)
    agent.conn.execute("INSERT INTO facts (subject, content) VALUES ('alex', 'prefers mornings')")
    agent.conn.execute("INSERT INTO chat_log (role, content) VALUES ('user', 'hello')")
    agent.conn.commit()
    lines = iter(["/memory"])

    def reader(prompt: str) -> str:
        try:
            return next(lines)
        except StopIteration:
            raise EOFError from None

    assert main(agent=agent, settings=settings, reader=reader) == 0
    out = " ".join(capsys.readouterr().out.split())
    assert "prefers mornings" in out
    assert "Unconsolidated messages: 1" in out


def test_a_turn_prints_steps_before_the_reply(home, capsys):
    from byo.app import Agent

    settings = load_settings(env={}, home=home)
    settings.ensure_home()
    agent = Agent(
        settings,
        adapter=script(tool_call("list_events", {"start": "2026-11-20"}), text("Nothing booked.")),
        memory=None,
    )
    lines = iter(["what is on friday"])

    def reader(prompt: str) -> str:
        try:
            return next(lines)
        except StopIteration:
            raise EOFError from None

    assert main(agent=agent, settings=settings, reader=reader) == 0
    out = capsys.readouterr().out
    assert out.index("tool · list_events") < out.index("Nothing booked.")


def test_a_transport_retry_is_announced_before_the_reply(home, capsys):
    from byo.app import Agent

    settings = load_settings(env={}, home=home)
    settings.ensure_home()
    agent = Agent(
        settings,
        adapter=script(error("Transport"), text("Back online.")),
        memory=None,
    )
    lines = iter(["hello"])

    def reader(prompt: str) -> str:
        try:
            return next(lines)
        except StopIteration:
            raise EOFError from None

    assert main(agent=agent, settings=settings, reader=reader) == 0
    out = capsys.readouterr().out
    assert "retry" in out and "transport hiccup" in out
    assert out.index("transport hiccup") < out.index("Back online.")
