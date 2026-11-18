"""Content parity: every pre-change label, count and action survives the restyle."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "byo" / "ops" / "static"

# T001 pinned inventory — mirrors contracts/surface-parity.md.
PINNED = [
    # navigation and shell
    "Overview", "Chat", "Observability", "Memory", "Settings", "byo",
    "Ask for something, or say what to remember", "Send",
    "theme-toggle", "theme: ",
    # overview
    "Today", "7 days", "All", "Agent idle",
    "A new turn is running", "return to the map",
    "Text view of the map", "Recent turns",
    "No turns recorded yet. Say something in the dock to start.",
    # chat cards
    "gate · ", "loop(s)", "tool(s)", "you ›", "byo ›",
    "call(s)", "in / ", "USD ", "Say something below to start.",
    # turn detail
    "Turn ", "Close", "slowest", "most $", "bad line(s) skipped",
    "loop ", "reply", "memory", "receipt", "recorded detail",
    "Raw record (", "delivered", "unfinished",
    # observability
    "turns", "tool calls", "spend", "Turns", "Spend by model",
    "model", "nothing spent yet", "No turns recorded yet.", "no timed steps",
    # memory
    "facts", "episodes", "mirror", "subject", "source", "when", "what",
    "forget", "nothing remembered yet", "no episodes yet",
    # settings
    "provider", "API key", "a key is set", "none set",
    "paste to replace, never shown again", "Save",
    # map words
    "idle", "running", "done", "skipped", "degraded", "failed",
    "not reached", "partial",
]


def _corpus() -> str:
    parts = [(STATIC / "index.html").read_text(encoding="utf-8")]
    for script in sorted((STATIC / "js").glob("*.js")):
        parts.append(script.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_every_pinned_label_survives():
    corpus = _corpus()
    missing = [label for label in PINNED if label not in corpus]
    assert not missing, missing
