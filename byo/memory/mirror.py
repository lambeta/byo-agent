"""The readable mirror: MEMORY.md plus one file per fact.

Mechanism: regenerate both from the database after every write. The database is the
source of truth; the files are a rendering a person can open and grep.

Rejected alternative: making the markdown files the store. Search over thousands of
files is slower and the UI would have to parse prose.
"""

from __future__ import annotations

from pathlib import Path


def fact_file(row) -> str:
    def one_line(value) -> str:
        return " ".join(str(value or "").split())

    return (
        f"---\nsubject: {one_line(row['subject'])}\nsource: {one_line(row['source'])}\n"
        f"created_at: {one_line(row['created_at'])}\n---\n{str(row['content']).strip()}\n"
    )


def rewrite(conn, settings) -> Path:
    settings.memory_dir.mkdir(parents=True, exist_ok=True)
    facts = conn.execute("SELECT * FROM facts ORDER BY id").fetchall()
    episodes = conn.execute("SELECT * FROM episodes ORDER BY id").fetchall()

    keep = {str(row["id"]) for row in facts}
    for stale in settings.memory_dir.glob("*.md"):
        if stale.stem not in keep:
            stale.unlink(missing_ok=True)
    for row in facts:
        (settings.memory_dir / f"{row['id']}.md").write_text(fact_file(row), encoding="utf-8")

    lines = ["# Memory", ""]
    lines.append(f"Facts ({len(facts)})")
    lines += [f"- [{row['subject']}] {row['content']}  _(id {row['id']})_" for row in facts]
    if not facts:
        lines.append("- none yet")
    lines += ["", f"Episodes ({len(episodes)})"]
    lines += [f"- {row['happened_at']} — {row['summary']}" for row in episodes]
    if not episodes:
        lines.append("- none yet")
    path = settings.mirror_path
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
