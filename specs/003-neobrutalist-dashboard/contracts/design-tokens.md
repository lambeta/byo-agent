# Contract: Design Tokens

**Date**: 2026-11-18 | **Plan**: [../plan.md](../plan.md) | **Model**: [../data-model.md](../data-model.md)

The token seam is the single public surface of the visual language. Component rules consume
tokens; they do not introduce raw hex, shadow or font values. A change to this file precedes a
change to the stylesheet, and `test_style_tokens.py` enforces both directions.

## Token table

Field and ink:

| Token | Dark value | Light value | Notes |
|---|---|---|---|
| `--byo-field` | `#101014` | `#fdf6e9` | page field; warm paper in light |
| `--byo-panel` | `#1a1a22` | `#ffffff` | card/panel fill |
| `--byo-panel-raised` | `#22222c` | `#fffdf5` | overlays: turn detail, raw record |
| `--byo-ink` | `#f2ede0` | `#1a1a1a` | contour + primary text; flips per scheme |
| `--byo-ink-soft` | `#b8b2a3` | `#4a4a4a` | secondary text on field/panel |
| `--byo-ink-on-accent` | `#1a1a1a` | `#1a1a1a` | text on saturated accent fills |

Accents (flat, saturated; dark values re-tuned to hold contrast on dark fills):

| Token | Dark value | Light value | Semantic role |
|---|---|---|---|
| `--byo-accent-brand` | `#ffd02f` | `#ffd02f` | brand mark, signature highlight |
| `--byo-accent-live` | `#6aa6ff` | `#4a7dff` | running state, primary action; light value tuned so `--byo-ink-on-accent` text holds 4.5:1 on it |
| `--byo-accent-ok` | `#57d19b` | `#1e9e62` | done/ok |
| `--byo-accent-bad` | `#ff7a7a` | `#ef5350` | failed/destructive; light value tuned so `--byo-ink-on-accent` text holds 4.5:1 on it |
| `--byo-accent-warn` | `#f2c14e` | `#c77f0a` | skipped/degraded/partial |

Contour, shadow, radius, motion:

| Token | Value (both schemes) | Notes |
|---|---|---|
| `--byo-contour-w` | `2px` | standard contour |
| `--byo-contour-w-strong` | `3.5px` | running + failed, primary action, focus ring base |
| `--byo-shadow-rest` | `4px 4px 0 var(--byo-ink)` | cards, overlays, composer |
| `--byo-shadow-press` | `1px 1px 0 var(--byo-ink)` | pressed; paired with `translate(3px,3px)` |
| `--byo-shadow-row` | `2px 2px 0 var(--byo-ink)` | list rows, chips, small controls |
| `--byo-shadow-double` | `5px 5px 0 var(--byo-accent-bad)` | failed emphasis (second cue after contour) |
| `--byo-radius` | `3px` | near-sharp; chips/pills excepted |
| `--byo-motion-fast` | `140ms` | state transitions only |

Type and space:

| Token | Value | Notes |
|---|---|---|
| `--byo-font-display` | `"Archivo Black","Arial Black","Helvetica Neue",system-ui,sans-serif` | weight 700–900; degrades gracefully |
| `--byo-font-body` | `system-ui,-apple-system,"Segoe UI",Roboto,sans-serif` | unchanged from today |
| `--byo-font-mono` | `ui-monospace,SFMono-Regular,Menlo,monospace` | unchanged from today |
| `--byo-text-1` | `14px` | body; never smaller |
| `--byo-text-2` | `12.5px` | dense data (steps, tables); never smaller |
| `--byo-text-3` | `11px` | micro-labels; uppercase + `--byo-track-wide` |
| `--byo-text-4` | `22px` | stat figures, display face |
| `--byo-track-wide` | `0.08em` | micro-label tracking |
| `--byo-space-1..4` | `6px / 10px / 16px / 24px` | 4-px rhythm; containers add shadow allowance |

## Contrast pairs (enforced per scheme)

Every pair is computed from the hex values above by `test_style_tokens.py` using the WCAG
relative-luminance formula. Levels: text AA 4.5:1; large text and interactive boundaries 3:1.

| Foreground | Background | Level | Schemes |
|---|---|---|---|
| `--byo-ink` | `--byo-field` | 4.5:1 | both |
| `--byo-ink` | `--byo-panel` | 4.5:1 | both |
| `--byo-ink-soft` | `--byo-panel` | 4.5:1 | both |
| `--byo-ink-on-accent` | each accent (5 pairs) | 4.5:1 | both |
| `--byo-ink` | `--byo-field` (contour vs field) | 3:1 | both |
| `--byo-accent-live` | `--byo-panel` (primary boundary) | 3:1 | both |
| `--byo-accent-bad` | `--byo-panel` (failed boundary) | 3:1 | both |

If a pair fails in a scheme, the accent's value in that scheme is re-tuned — never the level.

## Invariants

1. Every token is defined in the default (dark) block and re-valued in the
   `prefers-color-scheme: light` block; a token defined in only one scheme is a test failure.
2. Component rules reference `var(--byo-*)` for colour, shadow, contour width, radius and type
   geometry; a raw hex or raw `box-shadow` in a component rule is a test failure (the token
   definitions themselves are the only place hex appears).
3. No token or rule references an external resource: no `@import`, no `http(s)://`, no
   remote `url()`.
4. `--byo-text-1` and `--byo-text-2` never go below 14 px and 12.5 px (spec FR-004).
5. The light block is the `:root` default; the dark block is the `:root[data-theme="dark"]
   override selected by the in-shell theme switch (light default, persisted choice). Revised
   2026-11-19: previously dark was the default and light followed the OS media query.

## Change procedure

1. Edit this contract (add/rename/re-value a token, with rationale).
2. Update `style.css` to match.
3. Run `test_style_tokens.py` and `test_style_states.py`; both must pass.
4. If an accent value moved, re-run the quickstart contrast and grayscale scenarios.
