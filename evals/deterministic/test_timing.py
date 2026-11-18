"""A step reaches the surface while the turn is still running (SC-002)."""

from __future__ import annotations

import time

from scripted import script, text, tool_call

from byo.app import Agent
from byo.tools.registry import Tool


def test_every_step_precedes_the_reply_across_a_corpus(settings):
    first_step_ms: list[float] = []
    for index in range(10):
        agent = Agent(settings, adapter=script(text(f"answer {index}")), memory=None)
        seen: list[tuple[str, float]] = []
        started = time.perf_counter()

        def observer(kind: str, event: dict, seen=seen, started=started) -> None:
            seen.append((kind, (time.perf_counter() - started) * 1000))

        agent.respond("hello", observer=observer)
        assert seen, "a turn always produces at least one step"
        assert seen[0][0] == "llm_start"
        first_step_ms.append(seen[0][1])
        agent.close()
    assert len(first_step_ms) == 10
    assert max(first_step_ms) < 2000


def test_a_slow_tool_is_visible_before_the_reply(settings):
    agent = Agent(settings, adapter=script(tool_call("slow", {}), text("done")), memory=None)

    def slow() -> str:
        time.sleep(0.2)
        return "slept"

    agent.tools.register(Tool("slow", "sleep a moment", {"type": "object", "properties": {}}, slow))
    seen: list[tuple[str, dict]] = []
    started = time.perf_counter()
    result = agent.respond(
        "do the slow thing", observer=lambda kind, event: seen.append((kind, event))
    )
    elapsed = time.perf_counter() - started

    kinds = [kind for kind, _ in seen]
    assert kinds.index("tool") < kinds.index("llm", kinds.index("tool"))
    tool_event = next(event for kind, event in seen if kind == "tool")
    assert tool_event["duration_ms"] >= 150
    assert result.reply == "done"
    assert elapsed < 2.0
