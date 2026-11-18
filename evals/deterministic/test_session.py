"""Working memory: the persona file, the clock, and the history bound."""

from __future__ import annotations

from datetime import UTC, datetime

from byo.loop.types import Message
from byo.runtime.session import Session


class FixedClock:
    def __call__(self) -> datetime:
        return datetime(2026, 11, 18, 16, 30, tzinfo=UTC)


def test_persona_is_created_on_first_turn(settings):
    assert not settings.persona_path.exists()
    Session(settings, clock=FixedClock()).build_system("hi")
    assert settings.persona_path.exists()
    assert "personal assistant" in settings.persona_path.read_text(encoding="utf-8")


def test_system_prompt_carries_clock_and_model(settings):
    system = Session(settings, clock=FixedClock()).build_system("hi")
    assert "Right now it is Wednesday, 2026-11-18 16:30" in system
    assert settings.provider in system
    assert settings.effective_model() in system


def test_history_is_bounded_by_turns(settings):
    session = Session(settings, clock=FixedClock())
    for index in range(40):
        session.note_user(f"user {index}")
        session.note_assistant(f"assistant {index}")
    assert len(session.history) == settings.history_turns * 2
    assert session.history[-1].text() == "assistant 39"
    assert all(isinstance(message, Message) for message in session.history)
