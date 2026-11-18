"""The eight runtime states keep non-hue cues; interaction and media guards exist."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSS = (ROOT / "byo" / "ops" / "static" / "style.css").read_text(encoding="utf-8")

# data-state attribute vocabulary (T002 constant, from js renderers).
STATES = ["idle", "live", "done", "skipped", "degraded", "failed", "not-reached", "partial"]

NON_HUE = ("border", "stroke", "box-shadow", "filter", "opacity", "dasharray")


def _state_blocks(state: str) -> str:
    parts = []
    for match in re.finditer(
        r'\[data-state="' + state + r'"\][^{]*\{([^}]*)\}', CSS
    ):
        parts.append(match.group(1))
    return "\n".join(parts)


def test_all_eight_states_have_selectors_with_non_hue_cues():
    for state in STATES:
        body = _state_blocks(state)
        assert body, state
        cues = sum(1 for prop in NON_HUE if prop in body)
        assert cues >= 1, (state, "no non-hue cue declarations")


def test_running_and_failed_use_the_strong_contour():
    for state in ("live", "failed"):
        body = _state_blocks(state)
        assert "--byo-contour-w-strong" in body or "3px" in body or "3.5px" in body, state


def test_dashed_states_carry_a_dash_pattern():
    for state in ("skipped", "degraded", "partial", "not-reached"):
        body = _state_blocks(state)
        assert "dashed" in body or "dasharray" in body, state


def test_focus_visible_covers_links_buttons_inputs_and_map_nodes():
    for selector in ("a", "button", "input", ".map-node"):
        pattern = re.escape(selector) + r"[^{]*:focus-visible"
        assert re.search(pattern, CSS), selector


def test_media_guards_present_and_no_ambient_animation():
    assert "prefers-color-scheme: light" in CSS
    assert "prefers-reduced-motion" in CSS
    assert "forced-colors" in CSS
    assert "@keyframes" not in CSS
    assert "infinite" not in CSS
