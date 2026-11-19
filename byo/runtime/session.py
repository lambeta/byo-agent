"""Working memory for one turn: persona, clock, memory and a bounded history.

Mechanism: the system prompt is assembled fresh on every turn from the persona file,
the local clock (with timezone), the active model and, when memory is wired, the
retrieved block. History is bounded by a configured turn count.

Rejected alternative: keeping the whole conversation. It grows without bound, costs
more every turn and eventually crowds out the instructions.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from byo.loop.types import Message, TextBlock

if TYPE_CHECKING:
    from byo.config import Settings

DEFAULT_PERSONA = """You are a personal assistant running locally on the user's machine.
You are concise, warm and honest about where things live.

Rules:
- Use create_event when the person wants to schedule something. Resolve relative
  dates yourself; the current date and time are given below.
- Use list_events when they ask what is on their calendar. You can read it.
- Use save_note only when they ask you to remember something.
- Use send_message to draft a message; it writes a file, it sends nothing.
- Use query_weather for current conditions or the next three days in a named place; say
  which place and local reading time the tool returned.
- If a tool already ran for this request, do not run it again; answer from its result.
- Every tool output says where its artifact landed. Repeat that truthfully.
"""

RULES = (
    "\nWhen a lookup of the same target fails twice, stop guessing: use the exact "
    "identifier the person gave, or ask for it."
)


class Session:
    def __init__(
        self,
        settings: Settings,
        memory=None,
        session_id: str = "default",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.memory = memory
        self.session_id = session_id
        self.history: list[Message] = []
        self._clock = clock or (lambda: datetime.now().astimezone())
        self.recalled = ""

    def persona(self) -> str:
        path = self.settings.persona_path
        if not path.exists():
            path.write_text(DEFAULT_PERSONA, encoding="utf-8")
        return path.read_text(encoding="utf-8")

    def build_system(self, user_message: str = "") -> str:
        now = self._clock()
        parts = [
            self.persona().strip(),
            f"\nRight now it is {now:%A, %Y-%m-%d %H:%M} ({now:%Z}, UTC{now:%z}).",
            (
                f"Your model: you are running on '{self.settings.effective_model()}' via the "
                f"'{self.settings.provider}' provider, inside byo-agent, a local-first agent."
            ),
            RULES,
        ]
        if self.memory is not None:
            block = self.memory.recall_block(user_message)
            if block:
                self.recalled = block
                parts.append(
                    "\nWhat you remember that may matter here (it came from your own store; "
                    f"trust it):\n{block}"
                )
        return "\n".join(parts)

    def note_user(self, text: str) -> None:
        self.history.append(Message.user(text))
        self.bound()

    def note_assistant(self, text: str) -> None:
        if text:
            self.history.append(Message("assistant", (TextBlock(text),)))
        self.bound()

    def bound(self) -> None:
        keep = max(2, self.settings.history_turns * 2)
        if len(self.history) > keep:
            self.history = self.history[-keep:]
