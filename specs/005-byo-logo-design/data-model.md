# Phase 1 Data Model: byo Logo & Wordmark

This feature's "data" is brand assets. Entities below carry the validation rules the deterministic
tests assert; file-level details live in [contracts/brand-assets.md](contracts/brand-assets.md).

## Entities

### Logo Master

The single source design of the "byo" mark (`brand/master-wordmark.svg`).

| Field | Rule | Source |
|-------|------|--------|
| wordmark text | exactly "byo", lowercase | FR-001 |
| typeface | Zilla Slab Bold — never Archivo Black or a lookalike | FR-002 |
| letterform form | SVG path outlines; no `<text>`, no font reference | FR-007, FR-009 |
| colour usage | theme vocabulary only: brand yellow, ink, ink-on-accent; no new palette | FR-003 |
| treatment | yellow sticker + ink contour + hard offset shadow; slight sticker tilt echoing the current header | FR-003 |
| clear space | ≥ half the sticker contour width on all sides | design rule (US2) |
| minimum size | wordmark: 24 px height on screen; below that the compact mark takes over | FR-004 |

### Variant

A context-fit rendering derived from the master. States: `authored` → `derived` → `integrated`
→ `verified` (a variant is verified only when its surface renders it and tests pass).

| Variant | File | Surface(s) | Size range | Scheme handling |
|---------|------|-----------|------------|-----------------|
| Inline wordmark | inline in `byo/ops/static/index.html` | dashboard header | ~24 px cap height | consumes `--byo-*` tokens (light + dark) |
| Served wordmark | `byo/ops/static/brand/wordmark.svg` | README header | any (vector) | self-contained sticker, scheme-independent |
| Compact mark | `byo/ops/static/brand/mark.svg` | favicon, collapsed rail | 16–64 px | self-contained sticker, scheme-independent |

Validation rules (all variants):
- Parses as XML; single root `<svg>` with explicit `viewBox` (FR-009).
- No `<text>`, `<image>`, `<script>`, `@font-face`, or external URL of any kind (FR-007).
- Derived from the master — letterform path data shared or scaled, not redrawn (US3).
- Foreground/background contrast ≥ 4.5:1 (ink on brand yellow — the pair is already enforced by
  `test_style_tokens.py` for the theme tokens the logo consumes) (FR-005).

### Surface

A place the logo appears.

| Surface | Variant used | Notes |
|---------|--------------|-------|
| Dashboard header (all views) | inline wordmark | replaces `.brand-sticker`; keeps `aria-label="byo"` |
| Collapsed rail | compact mark | replaces today's `display:none` on `.brand` |
| Browser tab icon | compact mark via `<link rel="icon" type="image/svg+xml">` | served at `/static/brand/mark.svg` |
| README header | served wordmark | referenced by relative repo path |
| Terminal chat / trajectory renderer | none (plain text) | explicitly out of scope (spec assumption) |

### Typeface Licence

| Field | Value |
|-------|-------|
| typeface | Zilla Slab (Bold weight used) |
| authors | Typotheque, for the Mozilla Foundation, 2017 |
| licence | SIL Open Font License 1.1 |
| recorded at | `brand/OFL.txt` beside `brand/ZillaSlab-Bold.ttf` |
| obligation | licence text kept with the font; reserved font name respected (no modified-font redistribution under the same name — we ship outlines, not a modified font) |

## Relationships

- Logo Master 1—N Variant (every variant traces to the master; FR-004).
- Variant N—1 Surface(s) (each surface uses exactly one designated variant; SC-006).
- Typeface Licence 1—1 Logo Master (the licence governs the font the master's outlines derive from; FR-008).
