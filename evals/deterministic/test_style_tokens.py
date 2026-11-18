"""The design-token seam: both schemes, computed contrast, no raw values."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSS = (ROOT / "byo" / "ops" / "static" / "style.css").read_text(encoding="utf-8")

# Tokens that exist once (structural) vs. re-valued per scheme (colour).
COLOUR_TOKENS = [
    "--byo-field", "--byo-panel", "--byo-panel-raised",
    "--byo-ink", "--byo-ink-soft", "--byo-ink-on-accent",
    "--byo-accent-brand", "--byo-accent-live", "--byo-accent-ok",
    "--byo-accent-bad", "--byo-accent-warn",
]
STRUCTURAL_TOKENS = [
    "--byo-contour-w", "--byo-contour-w-strong",
    "--byo-shadow-rest", "--byo-shadow-press", "--byo-shadow-row", "--byo-shadow-double",
    "--byo-radius", "--byo-motion-fast",
    "--byo-font-display", "--byo-font-body", "--byo-font-mono",
    "--byo-text-1", "--byo-text-2", "--byo-text-3", "--byo-text-4",
    "--byo-track-wide",
    "--byo-space-1", "--byo-space-2", "--byo-space-3", "--byo-space-4",
]

# (foreground, background, minimum ratio) — from contracts/design-tokens.md.
CONTRAST_PAIRS = [
    ("--byo-ink", "--byo-field", 4.5),
    ("--byo-ink", "--byo-panel", 4.5),
    ("--byo-ink-soft", "--byo-panel", 4.5),
    ("--byo-ink-on-accent", "--byo-accent-brand", 4.5),
    ("--byo-ink-on-accent", "--byo-accent-live", 4.5),
    ("--byo-ink-on-accent", "--byo-accent-ok", 4.5),
    ("--byo-ink-on-accent", "--byo-accent-bad", 4.5),
    ("--byo-ink-on-accent", "--byo-accent-warn", 4.5),
    ("--byo-ink", "--byo-field", 3.0),          # contour vs field
    ("--byo-accent-live", "--byo-panel", 3.0),  # primary boundary
    ("--byo-accent-bad", "--byo-panel", 3.0),   # failed boundary
]


def _blocks() -> tuple[str, str]:
    light = re.search(
        r"@media\s*\(prefers-color-scheme:\s*light\)\s*\{\s*:root\s*\{(.*?)\}",
        CSS, re.S,
    )
    assert light, "light scheme :root block missing"
    dark = re.search(r"^:root\s*\{(.*?)\}", CSS, re.S | re.M)
    assert dark, "dark scheme :root block missing"
    return dark.group(1), light.group(1)


def _scheme_values(block: str) -> dict[str, str]:
    return dict(re.findall(r"(--byo-[a-z0-9-]+)\s*:\s*([^;]+);", block))


def _luminance(hex_colour: str) -> float:
    hex_colour = hex_colour.lstrip("#")
    assert len(hex_colour) == 6, hex_colour
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _ratio(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    high, low = max(la, lb), min(la, lb)
    return (high + 0.05) / (low + 0.05)


def test_every_token_is_defined_and_colours_revalued_per_scheme():
    dark, light = _blocks()
    for token in STRUCTURAL_TOKENS + COLOUR_TOKENS:
        assert token in dark, ("dark", token)
    for token in COLOUR_TOKENS:
        assert token in light, ("light", token)


def test_contrast_pairs_meet_aa_in_both_schemes():
    dark, light = _blocks()
    for name, block in (("dark", dark), ("light", light)):
        values = _scheme_values(block)
        for fg, bg, minimum in CONTRAST_PAIRS:
            ratio = _ratio(values[fg].strip(), values[bg].strip())
            assert ratio >= minimum, (name, fg, bg, round(ratio, 2), minimum)


def test_type_floor_matches_prechange_sizes():
    dark, _ = _blocks()
    values = _scheme_values(dark)
    assert values["--byo-text-1"].strip() == "14px"
    assert values["--byo-text-2"].strip() == "12.5px"
    assert values["--byo-text-3"].strip() == "11px"

def _without_token_blocks() -> str:
    stripped = re.sub(r":root\s*\{[^}]*\}", "", CSS)
    return stripped


def test_no_raw_hex_outside_token_blocks():
    body = _without_token_blocks()
    leaks = re.findall(r"#[0-9a-fA-F]{3,8}\b", body)
    assert not leaks, leaks


def test_no_raw_box_shadow_outside_token_blocks():
    body = _without_token_blocks()
    for declaration in re.findall(r"box-shadow\s*:\s*([^;]+);", body):
        value = declaration.strip()
        assert value == "none" or "var(--byo-shadow-" in value, value
