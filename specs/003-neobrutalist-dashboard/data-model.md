# Data Model: Neobrutalist Dashboard Refresh

**Date**: 2026-11-18 | **Plan**: [plan.md](plan.md)

This feature introduces no application data. Its "model" is the design system itself: the token
set, the component inventory that consumes it, and the state-cue matrix. These are the entities a
reviewer, a test, or a future edit must be able to enumerate.

## 1. Design Token

A named custom property on `:root`, re-valued per appearance scheme. Tokens are the only
permitted source of colour, contour, shadow and type-geometry values in component rules.

| Field | Meaning | Validation |
|---|---|---|
| name | `--byo-*` custom property identifier | lowercase, hyphenated, prefixed `--byo-` |
| role | one of: field, ink, accent, contour, shadow, type, space, radius, motion | must be in the closed role list |
| light value | value when `prefers-color-scheme: light` | must exist for every token |
| dark value | value in the default (dark) block | must be defined for every token |
| contrast partner | the token it must hold AA against, if any | declared for every accent and ink pairing; computed >= 4.5:1 text / 3:1 large + boundaries |

**Token groups** (full values in [contracts/design-tokens.md](contracts/design-tokens.md)):

- **Field**: `--byo-field` (page), `--byo-panel` (card), `--byo-panel-raised` (overlay).
- **Ink**: `--byo-ink` (contour and primary text contour-colour), `--byo-ink-soft` (secondary
  text on field/panel), `--byo-ink-on-accent` (text on saturated fills).
- **Accents**: `--byo-accent-brand` (yellow), `--byo-accent-live` (blue), `--byo-accent-ok`
  (green), `--byo-accent-bad` (red), `--byo-accent-warn` (orange).
- **Contour**: `--byo-contour-w` (2 px), `--byo-contour-w-strong` (3.5 px).
- **Shadow**: `--byo-shadow-rest`, `--byo-shadow-press`, `--byo-shadow-row` (compact list
  variant), `--byo-shadow-double` (failed state).
- **Type**: `--byo-font-display`, `--byo-font-body`, `--byo-font-mono`; sizes
  `--byo-text-1`..`--byo-text-4` (body never below the pre-change 14 px / 12.5 px minimums);
  tracking `--byo-track-wide` for micro-labels.
- **Space**: `--byo-space-1`..`--byo-space-4` on the existing 4-px rhythm; padding allowance
  for shadow/focus non-clipping is a fixed part of each container rule.
- **Radius**: `--byo-radius` (near-sharp, <= 4 px); chips keep their pill shape as the one
  deliberate exception (a chip is a sticker, VD-006).
- **Motion**: `--byo-motion-fast` (<= 150 ms) for state transitions; removed under
  `prefers-reduced-motion`.

**State transition**: none — tokens are static per scheme. A token change is a design decision:
edit the token contract first, then the stylesheet, then run `test_style_tokens.py`.

## 2. Component (surface element)

A styled thing on the page. The inventory with its required treatments lives in
[contracts/surface-parity.md](contracts/surface-parity.md); each row names the surface, its
container rule, its interactive states, and any permitted markup hook.

| Field | Meaning | Validation |
|---|---|---|
| id | stable component name (e.g. `sidebar.brand`, `map.node`, `composer.send`) | unique across the inventory |
| surface | one of the 12 in-scope surfaces (5 views, sidebar, composer, 4 overlays, 3 system states) | must appear in the spec's scope list |
| contour | which contour token it draws with | required for every bounded component |
| shadow | which shadow token, if elevated | rows use the compact variant; overlays use resting |
| interactive states | subset of hover / pressed / focus-visible | focus-visible mandatory for every interactive component |
| markup hook | the class/wrapper the scripts may add, if any | must be enumerated; anything else is out of bounds |

## 3. Runtime State Cue

The visual encoding of one of the eight map/card states. Full matrix and interaction contract in
[contracts/state-cues.md](contracts/state-cues.md).

| Field | Meaning | Validation |
|---|---|---|
| state | idle / running / done / skipped / degraded / failed / not-reached / partial | closed set of eight; matches `data-state` values already emitted |
| word | the written state word shown beside the node/row | unchanged from current renderer output |
| contour cue | weight and dash pattern | word + contour + shadow must distinguish any pair of states without hue |
| shadow cue | shadow treatment | as above |
| hue cue | accent role | fourth cue only; never the sole distinguisher |

**Invariants enforced by tests**: every state has a `[data-state="..."]` selector in the
stylesheet; every state declares at least two non-hue cues; failed and running use the strong
contour.

## 4. Contrast Pair

A (foreground token, background token) pairing that must hold WCAG 2.1 AA.

| Field | Meaning | Validation |
|---|---|---|
| foreground | token used for text or an interactive boundary | must be a defined token |
| background | token it sits on | must be a defined token |
| level | AA-text (4.5:1) or AA-large/boundary (3:1) | computed from hex values by `test_style_tokens.py` in both schemes |

## Relationships

```text
Design Token ──consumed by──▶ Component ──renders──▶ Runtime State Cue
      │                          │
      └── paired in ──▶ Contrast Pair (checked per scheme)
```

- A component rule references tokens only; a hard-coded hex or shadow in a component rule is a
  defect the token test flags.
- The state-cue matrix rides on the existing `data-state` attributes emitted by `map.js`,
  `live.js` and `render.js`; no script changes its vocabulary.
- Contrast pairs are enumerated, not discovered: the contract lists every pair, and the test
  computes each from token values in both schemes.

## Validation Rules (from the spec)

- **FR-004**: `--byo-text-*` never below the pre-change sizes (14 px body, 12.5 px dense);
  four distinct levels exist and are visually separable (size, weight, tracking, case).
- **FR-005**: the state-cue matrix satisfies the pairwise non-hue rule above.
- **FR-012**: every enumerated contrast pair meets its level in both schemes.
- **FR-014**: no token resolves to a remote resource; no `url()` points outside the local
  server.
- **FR-016**: at most one accent-sticker component per region; stickers carry no data.
