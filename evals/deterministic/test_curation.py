"""Curation: validated human writes to facts, without HTTP in the way."""

from __future__ import annotations

import pytest

from byo.memory import curation
from byo.memory.semantic.store import FactStore


def make_store(conn) -> FactStore:
    return FactStore(conn)


def test_add_trims_and_records_person_origin(conn):
    fact = curation.add(make_store(conn), "  tea  ", "  green over black  ")
    assert fact["subject"] == "tea"
    assert fact["content"] == "green over black"
    assert fact["source"] == "user"
    assert fact["created_at"]


def test_subject_line_breaks_collapse_but_content_keeps_them(conn):
    fact = curation.add(make_store(conn), "tea\nmorning", "line one\nline two")
    assert fact["subject"] == "tea morning"
    assert fact["content"] == "line one\nline two"


@pytest.mark.parametrize(
    ("subject", "content", "field"),
    [
        ("", "content", "subject"),
        ("   ", "content", "subject"),
        ("subject", "", "content"),
        ("subject", "\n  ", "content"),
    ],
)
def test_empty_or_whitespace_fields_are_refused(conn, subject, content, field):
    with pytest.raises(curation.Refused) as info:
        curation.add(make_store(conn), subject, content)
    assert info.value.code == "fact_validation"
    assert info.value.field == field
    assert make_store(conn).count() == 0


def test_limits_are_inclusive_and_name_the_limit(conn):
    store = make_store(conn)
    boundary = curation.add(store, "s" * curation.SUBJECT_LIMIT, "c" * curation.CONTENT_LIMIT)
    assert len(boundary["subject"]) == 120
    assert len(boundary["content"]) == 2000

    with pytest.raises(curation.Refused) as subject_info:
        curation.add(store, "s" * 121, "another content")
    assert subject_info.value.field == "subject"
    assert "120" in subject_info.value.message

    with pytest.raises(curation.Refused) as content_info:
        curation.add(store, "another subject", "c" * 2001)
    assert content_info.value.field == "content"
    assert "2000" in content_info.value.message


def test_duplicate_detection_normalizes_case_and_whitespace(conn):
    store = make_store(conn)
    first = curation.add(store, "Tea", "Green  Over Black")
    with pytest.raises(curation.Refused) as info:
        curation.add(store, " tea ", "green over\nblack")
    assert info.value.code == "fact_duplicate"
    assert info.value.existing_id == first["id"]
    assert store.count() == 1


def test_same_subject_with_different_content_is_not_a_duplicate(conn):
    store = make_store(conn)
    curation.add(store, "tea", "green over black")
    curated = curation.add(store, "tea", "black over green")
    assert curated["id"]
    assert store.count() == 2


def test_edit_preserves_identity_origin_and_creation_time(conn):
    store = make_store(conn)
    fact_id = store.add("alex", "prefers mornings", source="tool")
    before = store.get(fact_id)

    updated = curation.edit(store, fact_id, "alex", "prefers afternoons")

    assert updated["id"] == fact_id
    assert updated["subject"] == "alex"
    assert updated["content"] == "prefers afternoons"
    assert updated["source"] == "tool"
    assert updated["created_at"] == before["created_at"]


def test_edit_can_change_subject_only_or_content_only(conn):
    store = make_store(conn)
    fact_id = store.add("tea", "green over black")

    curated = curation.edit(store, fact_id, "Tea (morning)", "green over black")
    assert curated["subject"] == "Tea (morning)"
    assert curated["content"] == "green over black"

    curated = curation.edit(store, fact_id, "Tea (morning)", "black over green")
    assert curated["subject"] == "Tea (morning)"
    assert curated["content"] == "black over green"


def test_edit_of_a_missing_fact_is_not_found(conn):
    with pytest.raises(curation.Refused) as info:
        curation.edit(make_store(conn), 99, "subject", "content")
    assert info.value.code == "fact_not_found"


def test_mismatched_baseline_is_a_conflict_and_writes_nothing(conn):
    store = make_store(conn)
    fact_id = store.add("tea", "green over black")
    with pytest.raises(curation.Refused) as info:
        curation.edit(
            store,
            fact_id,
            "tea",
            "black over green",
            baseline_subject="tea",
            baseline_content="something else",
        )
    assert info.value.code == "fact_conflict"
    assert store.get(fact_id)["content"] == "green over black"


def test_matching_baseline_updates(conn):
    store = make_store(conn)
    fact_id = store.add("tea", "green over black")
    updated = curation.edit(
        store,
        fact_id,
        "tea",
        "black over green",
        baseline_subject="tea",
        baseline_content="green over black",
    )
    assert updated["content"] == "black over green"


def test_omitted_baseline_edits_unconditionally(conn):
    store = make_store(conn)
    fact_id = store.add("tea", "green over black")
    updated = curation.edit(store, fact_id, "tea", "black over green")
    assert updated["content"] == "black over green"


def test_edit_onto_another_fact_duplicate_is_refused(conn):
    store = make_store(conn)
    keep = store.add("tea", "green over black")
    other = store.add("coffee", "black")
    with pytest.raises(curation.Refused) as info:
        curation.edit(store, other, "tea", "GREEN over black")
    assert info.value.code == "fact_duplicate"
    assert info.value.existing_id == keep
    assert store.get(other)["subject"] == "coffee"


def test_edit_may_keep_its_own_normalized_key(conn):
    store = make_store(conn)
    fact_id = store.add("Tea", "Green  Over Black")
    updated = curation.edit(store, fact_id, "tea", "green over black")
    assert updated["content"] == "green over black"


def test_edit_updates_the_recall_index(conn):
    store = make_store(conn)
    fact_id = curation.add(store, "alex", "prefers mornings")["id"]
    curation.edit(store, fact_id, "alex", "prefers afternoons")
    assert store.search("afternoons")[0]["content"] == "prefers afternoons"
    assert store.search("mornings") == []


def test_over_limit_legacy_fact_must_be_shortened_before_saving(conn):
    store = make_store(conn)
    fact_id = store.add("legacy", "x" * 2001)
    with pytest.raises(curation.Refused) as info:
        curation.edit(store, fact_id, "legacy", "x" * 2001)
    assert info.value.code == "fact_validation"
    assert info.value.field == "content"

    updated = curation.edit(store, fact_id, "legacy", "short enough")
    assert updated["content"] == "short enough"
