"""Redaction is enforced in the sink, by key and by value shape."""

from __future__ import annotations

from byo.ops.trajectory import Trajectory, redact


def test_key_names_are_redacted():
    assert redact({"api_key": "x"})["api_key"] == "[redacted]"
    assert redact({"Authorization": "Bearer abc"})["Authorization"] == "[redacted]"
    assert redact({"nested": {"token": "abc"}})["nested"]["token"] == "[redacted]"


def test_value_shapes_are_redacted():
    text = redact({"output": "key sk-ant-abcdefgh12345678 leaked"})
    assert "sk-ant-" not in text["output"]
    assert "[redacted]" in text["output"]


def test_redaction_is_idempotent():
    value = {"content": "sk-ant-abcdefgh12345678", "api_key": "x"}
    assert redact(redact(value)) == redact(value)


def test_the_terminal_never_prints_a_secret(settings, capsys):
    from scripted import script, text, tool_call

    from byo.app import Agent
    from byo.gateway.cli import step_observer
    from byo.tools.registry import Tool

    adapter = script(tool_call("leaky", {}), text("done"))
    agent = Agent(settings, adapter=adapter, memory=None)
    agent.tools.register(
        Tool(
            "leaky",
            "returns a key-shaped string",
            {"type": "object", "properties": {}},
            lambda: "the key is sk-ant-abcdefgh12345678",
        )
    )
    agent.respond("go", observer=step_observer())
    out = capsys.readouterr().out
    assert "sk-ant-" not in out
    assert "[redacted]" in out


def test_nothing_sensitive_reaches_the_file(settings):
    settings.ensure_home()
    sink = Trajectory(settings)
    sink.start("my key is sk-ant-abcdefgh12345678", source="cli")
    sink.record("tool", tool="echo", args={"api_key": "abc", "value": "sk-ant-abcdefgh12345678"})
    sink.end("done", 1)
    written = "".join(
        path.read_text(encoding="utf-8") for path in settings.trajectories_dir.glob("*.jsonl")
    )
    assert "sk-ant-" not in written
    assert "abcdefgh12345678" not in written
    assert "[redacted]" in written


def test_long_strings_are_truncated():
    from byo.ops.trajectory import MAX_STRING

    value = redact({"output": "x" * (MAX_STRING + 100)})["output"]
    assert value.endswith("[…truncated]")
    assert len(value) == MAX_STRING + len("[…truncated]")
