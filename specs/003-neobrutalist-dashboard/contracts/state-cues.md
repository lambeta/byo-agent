# Contract: Runtime State Cues and Interaction States

**Date**: 2026-11-18 | **Plan**: [../plan.md](../plan.md) | **Model**: [../data-model.md](../data-model.md)

The eight runtime states are emitted as `data-state` attributes by the existing renderers
(`map.js`, `live.js`, `render.js`, `dock.js`). This contract fixes how each state is
*drawn* so that no state depends on hue alone (spec FR-005), and how interactive elements behave
across resting, hover, pressed and focus-visible (spec FR-008).

## State-cue matrix

Cue kit: **word** (always rendered), **contour** (weight / dash), **shadow** (treatment),
**hue** (accent role — fourth cue only).

| State | Word | Contour cue | Shadow cue | Hue cue |
|---|---|---|---|---|
| idle | idle | 2 px solid | none (map node) / row shadow (lists) | ink |
| running | running | 3.5 px solid | resting shadow + flat live-accent fill | live |
| done | done | 2 px solid, ok-coloured contour | none | ok |
| skipped | skipped | 2 px dashed `4 3` | none | warn |
| degraded | degraded | 2 px dashed `4 3` | none | warn |
| partial | partial | 2 px dashed `4 3` | row shadow | warn |
| failed | failed | 3.5 px solid, bad-coloured contour | double bad-coloured shadow | bad |
| not-reached | not reached | 2 px dashed `4 3` | none; opacity 0.45 (kept) | ink |

Pairwise rule: any two states differ in word **and** at least two of {contour weight, dash
pattern, shadow treatment}. Skipped/degraded/partial share a dash pattern by design — they are
distinguished by their word and, for partial, its shadow; that satisfies the rule because the
word is always present.

Selectors: `.map-node[data-state="running"]`, `.chip[data-state="failed"]`,
`.recent-state[data-state="unfinished"]`, etc. — the existing attribute hooks are sufficient;
no script changes vocabulary.

## Edges

| Edge state | Cue |
|---|---|
| idle | 1.4 px ink-soft stroke |
| running (live) | 2.4 px live-accent stroke (weight, not glow) |

## Interaction states (all interactive elements)

| State | Treatment |
|---|---|
| resting | contour + shadow per component inventory |
| hover | shadow offset +1 px **or** accent-fill swap; never blur, never scale |
| pressed (active) | `--byo-shadow-press` + `translate(3px,3px)` — the control moves onto its shadow |
| focus-visible | 3.5 px `--byo-accent-live` outline with 2 px offset **plus** the element's own contour — a double ring that stays visible on any fill; never clipped (containers carry shadow/focus padding allowance) |
| disabled | dashed contour, `--byo-ink-soft` text, no shadow, no hover response |

Focus order follows the DOM: navigation → composer → view content → overlay close control.
Closing the turn-detail overlay returns focus to the element that opened it (existing behavior,
preserved).

## Media-query behavior

- **`prefers-reduced-motion: reduce`**: all transitions and the press translation are removed;
  state changes are instant. Already present for map nodes/edges; extended to every rule that
  gains a transition.
- **`forced-colors: active`**: shadows are dropped (the platform ignores them anyway),
  contours rely on weight and dash pattern alone, and text/background resolve to system colors.
  The eight states remain pairwise distinguishable without hue because word, weight and dash
  survive forced colours.
- **`prefers-color-scheme: light`**: token re-valuation only; no rule is scheme-specific beyond
  tokens.

## Invariants (tested)

1. All eight `[data-state]` selectors exist in `style.css` with their contour and shadow
   declarations.
2. `:focus-visible` rules exist for links, buttons, inputs and `.map-node`.
3. The three media queries exist; the reduced-motion block covers every transitioned property.
4. No rule animates anything other than the declared state transitions (no keyframes, no
   infinite animation) — scanned by `test_style_states.py`.
