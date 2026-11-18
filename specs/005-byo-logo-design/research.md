# Phase 0 Research: byo Logo & Wordmark

All spec-level unknowns resolved here. The spec deliberately left two decisions to planning:
the wordmark typeface (FR-002 says only "visibly distinct from Archivo Black") and the rendering
strategy that satisfies local-first (FR-007) with readable sources (FR-009).

## Decision 1: Wordmark typeface — Zilla Slab Bold

**Decision**: Set the "byo" wordmark in **Zilla Slab Bold** (Typotheque for Mozilla, 2017),
licensed **SIL Open Font License 1.1** — verified on
[Google Fonts](https://fonts.google.com/specimen/Zilla+Slab/license) and the
[AOSP mirror](https://android.git.googlesource.com/platform/external/google-fonts/zilla-slab/+/refs/tags/android-vts-15.0_r2/LICENSE).
OFL 1.1 permits bundling and embedding (including conversion to outlines) with the licence text
kept alongside the font; that record lands at `brand/OFL.txt`.

**Rationale**:
- **Distinct from Archivo Black** (FR-002): Archivo Black is a heavy geometric *grotesque* sans;
  Zilla Slab is a *slab serif* — a different genre, immediately distinguishable in a side-by-side
  (SC-002). Its bracketed block serifs give "byo" a constructed, engineered character.
- **Theme-coherent** (FR-003): slab serifs are the poster/print tradition neobrutalism draws from;
  the square serifs rhyme with the theme's hard contours and offset shadows.
- **Positioning-coherent**: an industrial, blueprint-adjacent voice for a product that is "built,
  not configured" and "readable in an afternoon".
- **Legible when outlined**: Bold weight keeps strokes thick enough to survive path-outlining and
  down-scaling.

**Alternatives considered**:
- *Bungee* (OFL): strong sticker vibe but signage-gimmicky; poor letterfit at small sizes. Rejected.
- *Space Mono Bold* (OFL): monospace collides with the dashboard's mono used for data labels — the
  wordmark would read as a label, not a brand. Rejected.
- *Bricolage Grotesque* (OFL): characterful but still a grotesque — too close to Archivo Black to
  pass "visibly distinct" comfortably. Rejected.
- *Hand-drawn custom letterforms*: the user explicitly asked for a font change (换字体), and
  custom lettering without a type designer risks an amateur mark. Rejected (noted: letterforms are
  still hand-tuned after outlining, but they start from a real typeface).

## Decision 2: Runtime rendering — outlined SVG paths, inline for the header

**Decision**: The wordmark ships as **SVG path outlines** (glyphs converted from Zilla Slab Bold
once, at authoring time, then hand-tuned). The dashboard header inlines that SVG so it consumes
`--byo-*` tokens; served variants (`wordmark.svg`, `mark.svg`) are self-contained stickers
with baked theme-safe colours. No `@font-face`, no `<text>`, no runtime font loading anywhere.

**Rationale**:
- **Theming**: the dashboard theme is a manual `data-theme` attribute, not OS
  `prefers-color-scheme`. An external `<img>` SVG cannot see page tokens or that attribute;
  inline SVG can. Conversely README/favicon hosts need a scheme-independent asset — the sticker
  carries its own yellow field + ink contour, so baked colours work on any background.
- **Offline & zero-CLS** (FR-007, SC-004): paths are deterministic bytes; no font fetch, no
  swap, no fallback-that-loses-the-name (spec edge case).
- **Testable offline**: structure is assertable with stdlib XML parsing (see contracts).

**Alternatives considered**:
- *Runtime `@font-face` + live text*: font-display swap causes CLS; a failed font load falls back
  to the very fonts the logo must be distinct from; adds a binary to the served tree (breaks
  `test_style_offline.py`, which reads every served file as UTF-8). Rejected.
- *`<img>` everywhere*: cannot theme with the manual dark scheme; header would need two swapped
  files and a flash risk. Rejected for the header (kept for README, where tokens don't exist anyway).

## Decision 3: Asset topology — two zones, one master

**Decision**: Repo-root `brand/` = sources (master SVG, vendored `zilla-slab-bold.woff2`,
`OFL.txt`, design note). `byo/ops/static/brand/` = two derived served SVGs. Derivations are
documented, repeatable by hand (no build tool), and asserted by tests.

**Rationale**: keeps binaries out of the served tree and the wheel; satisfies FR-008 (licence next
to font) and FR-009 (readable masters); one master prevents variant drift (US3).

**Alternatives considered**: *single `brand/` under static* (would serve the binary font and break
the offline test) — rejected; *assets only under static with font in git LFS* (new tooling for one
file) — rejected.

## Decision 4: Compact mark & surfaces

**Decision**: Compact mark = the yellow sticker squared, carrying a single Zilla Slab Bold **"b"**
(the wordmark's initial, same outlines). Used for the favicon and the collapsed rail (which today
hides the brand entirely — an improvement the spec's AC1.4 permits). README shows the full
wordmark. Terminal stays plain text (spec assumption).

**Alternatives considered**: *full "byo" squeezed into the favicon* (illegible at 16 px) — rejected;
*abstract geometric mark* (fails SC-003 "recognisable as byo") — rejected.
