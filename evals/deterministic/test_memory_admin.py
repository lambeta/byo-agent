"""manage_memory and update_persona through the registry."""

from __future__ import annotations

from scripted import script

from byo.memory import Memory
from byo.tools import build_registry


def registry(settings, conn):
    memory = Memory(conn, settings, script())
    return build_registry(conn, settings, memory=memory), memory


def test_list_edit_forget(settings, conn):
    tools, memory = registry(settings, conn)
    fact_id = memory.facts.add("alex", "prefers mornings")
    assert "alex" in tools.execute("manage_memory", {"action": "list"})
    tools.execute(
        "manage_memory",
        {"action": "edit", "id": fact_id, "subject": "alex", "content": "prefers afternoons"},
    )
    assert memory.facts.get(fact_id)["content"] == "prefers afternoons"
    out = tools.execute("manage_memory", {"action": "forget", "id": fact_id})
    assert "Forgot fact" in out
    assert memory.facts.count() == 0


def test_unknown_id_is_text_not_an_error(settings, conn):
    tools, _ = registry(settings, conn)
    assert tools.execute("manage_memory", {"action": "forget", "id": 99}) == "No fact with id 99."


def test_update_persona_keeps_a_backup(settings, conn):
    tools, _ = registry(settings, conn)
    settings.persona_path.write_text("old persona\n", encoding="utf-8")
    out = tools.execute("update_persona", {"content": "new persona"})
    assert "Persona saved" in out
    assert settings.persona_path.read_text(encoding="utf-8").strip() == "new persona"
    assert (
        settings.persona_path.with_suffix(".md.bak").read_text(encoding="utf-8").strip()
        == "old persona"
    )


def test_list_reports_empty_memory(settings, conn):
    tools, _ = registry(settings, conn)
    assert tools.execute("manage_memory", {"action": "list"}) == "No facts yet."


def test_edit_needs_all_three_fields(settings, conn):
    tools, memory = registry(settings, conn)
    fact_id = memory.facts.add("alex", "prefers mornings")
    out = tools.execute("manage_memory", {"action": "edit", "id": fact_id, "subject": "alex"})
    assert out == "Error: ValueError: edit needs id, subject and content"
    assert memory.facts.get(fact_id)["content"] == "prefers mornings"


def test_edit_rejects_whitespace_only_values(settings, conn):
    tools, memory = registry(settings, conn)
    fact_id = memory.facts.add("alex", "prefers mornings")
    out = tools.execute(
        "manage_memory", {"action": "edit", "id": fact_id, "subject": "   ", "content": "  "}
    )
    assert out == "Error: ValueError: edit needs id, subject and content"
    fact = memory.facts.get(fact_id)
    assert fact["subject"] == "alex"
    assert fact["content"] == "prefers mornings"


def test_edit_unknown_id_is_text_not_an_error(settings, conn):
    tools, _ = registry(settings, conn)
    out = tools.execute(
        "manage_memory", {"action": "edit", "id": 99, "subject": "a", "content": "b"}
    )
    assert out == "No fact with id 99."


def test_forget_needs_an_id(settings, conn):
    tools, _ = registry(settings, conn)
    out = tools.execute("manage_memory", {"action": "forget"})
    assert out == "Error: ValueError: forget needs id"


def test_unknown_action_is_an_error(settings, conn):
    tools, _ = registry(settings, conn)
    out = tools.execute("manage_memory", {"action": "purge"})
    assert out == "Error: ValueError: unknown action 'purge'"


def test_update_persona_rejects_empty_content(settings, conn):
    tools, _ = registry(settings, conn)
    out = tools.execute("update_persona", {"content": "   "})
    assert out == "Error: ValueError: content cannot be empty"
    assert not settings.persona_path.exists()
