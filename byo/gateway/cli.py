"""Terminal chat — the zero-setup surface.

Mechanism: read a line, run one turn, print the steps as they happen, then the reply.
The observer is the only coupling to the loop, so this file never learns what a tool is.

Rejected alternative: printing the reply and a summary at the end. The whole point is
that a person can watch the turn while it runs.
"""

from __future__ import annotations

from collections.abc import Callable

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

from byo.app import Agent
from byo.config import Settings, load_settings, missing_key_message
from byo.ops.trajectory import redact

console = Console()

PREVIEW = 80


def _short(value) -> str:
    text = value if isinstance(value, str) else str(value)
    text = " ".join(text.split())
    return text if len(text) <= PREVIEW else text[: PREVIEW - 1] + "…"


def step_observer(out: Console | None = None) -> Callable[[str, dict], None]:
    out = out or console

    def observe(kind: str, event: dict) -> None:
        event = redact(event)
        if kind == "tool":
            args = event.get("args") or {}
            rendered = escape(", ".join(f"{k}={_short(v)}" for k, v in args.items()))
            name = escape(str(event.get("tool")))
            output = escape(_short(event.get("output", "")))
            out.print(f"  [dim]tool · {name}({rendered}) → {output}[/dim]")
        elif kind == "gate":
            decision = escape(str(event.get("decision")))
            reason = escape(str(event.get("reason", "")))
            out.print(f"  [dim]gate · {decision} — {reason}[/dim]")
        elif kind == "retry":
            model = escape(str(event.get("model", "?")))
            out.print(f"  [dim]retry · {model} · transport hiccup[/dim]")
        elif kind == "llm" and event.get("kind") == "final":
            out.print("  [dim]llm · final answer after the step limit[/dim]")
        elif kind == "error":
            stage = escape(str(event.get("stage")))
            message = escape(str(event.get("message")))
            out.print(f"  [red]{stage} · {message}[/red]")

    return observe


def memory_snapshot(agent: Agent) -> str:
    conn = agent.conn
    facts = conn.execute("SELECT subject, content FROM facts ORDER BY id DESC LIMIT 8").fetchall()
    episodes = conn.execute(
        "SELECT happened_at, summary FROM episodes ORDER BY id DESC LIMIT 5"
    ).fetchall()
    pending = conn.execute("SELECT COUNT(*) FROM chat_log WHERE consolidated = 0").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    lines = [f"Facts ({total})"]
    lines += [f"- [{row['subject']}] {row['content']}" for row in facts] or ["- none yet"]
    lines += ["", "Recent episodes"]
    lines += [f"- {row['happened_at']} · {row['summary']}" for row in episodes] or ["- none yet"]
    lines += ["", f"Unconsolidated messages: {pending}"]
    return "\n".join(lines)


def main(
    reader: Callable[[str], str] | None = None,
    agent: Agent | None = None,
    settings: Settings | None = None,
) -> int:
    settings = settings or load_settings()
    if agent is None and not settings.api_key:
        console.print(missing_key_message(settings))
        return 2
    if agent is None:
        try:
            settings.ensure_home()
            agent = Agent(settings)
        except OSError as exc:
            console.print(f"Cannot use {settings.home}: {exc}")
            return 2

    console.print(
        Panel.fit(
            "[bold]byo[/bold] — local, yours, transparent.\n"
            f"home: {settings.home.resolve()}   model: {settings.effective_model()}\n"
            "Commands: /memory · /quit",
            border_style="cyan",
        )
    )
    reader = reader or (lambda prompt: input(prompt))
    observer = step_observer(console)
    while True:
        try:
            line = reader("you › ")
        except (EOFError, KeyboardInterrupt):
            break
        text = (line or "").strip()
        if not text:
            continue
        if text in ("/quit", "/exit"):
            break
        if text == "/memory":
            console.print(Panel(memory_snapshot(agent), title="Memory", border_style="cyan"))
            continue
        result = agent.respond(text, observer=observer, source="cli")
        console.print(f"[bold green]byo ›[/bold green] {result.reply}\n")
    agent.close()
    console.print("[dim]bye — your data stays in the home directory[/dim]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
