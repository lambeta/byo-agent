# Quickstart: Neobrutalist Dashboard Refresh

**Date**: 2026-11-18 | **Plan**: [plan.md](plan.md) | **Contracts**: [contracts/](contracts/)

Runnable validation scenarios that prove the restyle works end-to-end. Each scenario names its
setup, its steps and its expected outcome, and maps to the spec's success criteria. Run the
deterministic suite first; then walk the browser scenarios in order.

## 0. Prerequisites

```bash
uv venv && uv pip install -e ".[dev]"   # once
export BYO_API_KEY=...                   # only for the live-turn scenario (4)
```

No browser tooling, no build step, no network beyond the initial install. Scenario 4 is the only
one that needs a model key; everything else runs against the scripted/offline paths.

## 1. Deterministic suite (offline)

```bash
make eval        # or: uv run pytest evals/deterministic -q
make gate
```

**Expected**: the whole suite passes, including the new `test_style_tokens.py`,
`test_style_states.py`, `test_style_offline.py` and the extended `test_map_static.py` —
token completeness in both schemes, computed contrast pairs at AA, the eight state selectors,
the three media queries, zero external URLs, and the pinned label parity list. Covers SC-002,
SC-003 (computed part), SC-010 (static part), FR-004, FR-005 (selector part), FR-014, FR-015.

## 2. Serve and walk the five views

```bash
uv run byo dashboard    # http://127.0.0.1:7777
```

Open the URL. Walk Overview → Chat → Observability → Memory → Settings.

**Expected**: every surface from [contracts/surface-parity.md](contracts/surface-parity.md)
carries the new language — 2 px ink contours, hard offset shadows, flat accent blocks, display
face on brand/titles/figures, near-sharp corners — and no region shows the previous thin-border
look. Every parity label in the contract is present. First paint feels instant (< 1 s, SC-009).
Covers SC-001, SC-002 (visual pass).

## 3. Both appearance schemes

Toggle the OS appearance (macOS: System Settings → Appearance) with the dashboard open; repeat
the five-view walk in the other scheme.

**Expected**: the identity is recognisably the same in both — contours flip from near-black to
paper, panels re-fill, accents re-value — and nothing loses contrast or hierarchy. Sample one
body-text pair and one accent pair with a contrast picker (e.g. the browser inspector's contrast
readout) in each scheme: body >= 4.5:1, interactive boundaries >= 3:1. Covers FR-011, FR-012,
SC-003 (sampled part).

## 4. Live turn on the new fills (needs BYO_API_KEY)

With the dashboard open on Overview, send a message from the terminal in another window
(`uv run byo`) and one from the browser composer.

**Expected**: nodes and edges light in order on both turns; the running state reads as a flat
accent fill plus heavier contour (no glow, no translucency); the status pill names each step; the
page does not reflow as highlights fire; after the turn, the map settles to idle and the last
turn's summaries remain readable. In the composer, keystroke echo feels immediate while steps
stream (< 100 ms, SC-009). Covers SC-007, FR-006, FR-009, VD-003/VD-007.

No key available? Substitute: replay a fixture turn with the scripted model
(`evals/scripted.py`) against a temporary home and watch the same lighting.

## 5. Keyboard-only pass

Unplug the mouse mentally: Tab from the top through Overview, open a map node with Enter, open a
recent turn, close the detail, switch windows, tab through Settings, submit a chat message with
Enter.

**Expected**: a visible double-ring focus indicator at every stop, never clipped by a container
edge; every action operable; focus returns to the opening element when the detail closes; nothing
is reachable by mouse only. Covers SC-005, FR-008.

## 6. Reflow and zoom

Resize the window to 1280, 900 and 375 px wide; then at 1280 set browser zoom to 200%.

**Expected**: at 1280/900 the layout holds with no page-level horizontal scroll; at 375 the
sidebar and views stack to a single column, primary targets (send, nav, window buttons, close,
forget, save) remain >= 40 px and operable, and the map keeps its own internal scroll region as
the only horizontal scroller; at 200% zoom no text clips and no controls overlap. Covers SC-004,
FR-010, FR-017.

## 7. Grayscale state naming

Capture the map (screenshot or print preview) and view it desaturated (macOS: Preview → Tools →
Adjust Color → saturation 0, or a grayscale display filter).

**Expected**: all eight state words plus their contour/dash/shadow cues let you name every
state without hue — idle vs running vs done vs skipped/degraded/partial vs failed vs
not-reached. If any pair is confusable, the state-cue contract has failed. Covers SC-006, FR-005.

## 8. Edge-case sweep

- Fresh temporary home (`BYO_HOME=$(mktemp -d) uv run byo dashboard`): every empty state
  renders in the new language and still says what to do next (SC-011, FR-013).
- Stop the event feed (kill the dashboard mid-poll, restart): the status pill shows the
  reconnecting/error treatment without the page looking broken (FR-013).
- Open a turn detail, then start a new turn from the terminal: the detail stays put, the live
  indicator offers return, both readable (edge case: live while reading history).
- Enable forced colours (Windows HC mode, or emulate in devtools): contours, words and focus
  survive; no information disappears (FR-012).
- Paste a very long string into the composer and send it against the scripted model: the card
  wraps, no horizontal page scroll (US2.4).

## 9. Content parity walkthrough

With [contracts/surface-parity.md](contracts/surface-parity.md) open beside the browser, tick
every pinned label, count and action on a single pass through the five views plus a turn detail.

**Expected**: 100% present, none hidden behind hover, none reordered into a different meaning.
Covers SC-002.

## Done when

Scenarios 1–3, 5–9 pass with no key, and scenario 4 (or its scripted substitute) passes; the
token, cue and parity contracts match what is on screen; and `make gate` is green.
