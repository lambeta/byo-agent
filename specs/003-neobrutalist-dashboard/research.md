# Phase 0 Research: Neobrutalist Dashboard Refresh

**Date**: 2026-11-18 | **Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Every unknown from the Technical Context is resolved below. Because the constitution fixes the
stack (plain HTML/CSS/JS, no build step, no new dependency) and the spec fixes the visual
direction (VD-001..VD-008), research narrows to *how* to express that direction inside those
constraints, and how to verify it without a browser test runner.

## R1 — Styling mechanism: one token-driven stylesheet

- **Decision**: Keep a single `style.css`. Define the whole visual language as CSS custom
  properties on `:root` (the *tokens*), re-value them inside the existing
  `@media (prefers-color-scheme: light)` block for the light scheme, and write component rules
  that consume only tokens. Add the two missing guards — `prefers-reduced-motion` (exists) and
  `forced-colors` (new).
- **Rationale**: One file, one token seam, two schemes from the same definitions — there is no
  second source to drift, and a reviewer reads the entire identity in one place. Custom
  properties are supported by every target browser and need no tooling.
- **Alternatives considered**: (a) *A CSS framework or utility library* (Tailwind, UnoCSS) —
  rejected: new dependency, build step, and a config file owning the design; violates the
  constitution's dependency budget and the spec's no-build constraint. (b) *Two stylesheets, one
  per scheme* — rejected: double maintenance, guaranteed drift. (c) *A runtime theme switch with
  a class toggle* — rejected: spec FR-011 requires following the OS with no new control.
  (d) *Inline styles per component* — rejected: untestable, unreviewable, kills the token seam.

## R2 — Display typography without a webfont

- **Decision**: Use curated system font stacks. Display level (brand, page titles, large
  figures): a heavy grotesque stack — `"Archivo Black", "Arial Black", "Helvetica Neue",
  system-ui, sans-serif` at weight 700–900 — where the first named faces are used only if
  already installed and the stack degrades gracefully. Body: the existing `system-ui` stack.
  Recorded values: the existing `ui-monospace` stack. Micro-labels: uppercase with
  `letter-spacing` and weight 700.
- **Rationale**: Spec FR-014 forbids any network request for fonts; spec Assumptions prefer no
  binary asset in the repository. System stacks satisfy both, render instantly, and the heavy
  grotesque voices (Arial Black on macOS/Windows, Helvetica Neue bold on macOS) already deliver
  the brutalist poster weight. The stack degrades to `system-ui` bold, which still carries the
  hierarchy because hierarchy comes from size, weight, tracking and contour — not from one
  specific face.
- **Alternatives considered**: (a) *Bundle an open-license woff2* (e.g. Archivo Black, Inter) —
  rejected: a binary asset in a repo that currently has none, a second serving path, and a
  license file to maintain; the marginal gain over Arial Black does not pay for it. (b) *Google
  Fonts / CDN link* — rejected: violates FR-014 outright. (c) *Variable system fonts via
  `font-variation-settings`* — rejected: inconsistent across platforms, untestable here.

## R3 — Contour colour as a token (`--ink`)

- **Decision**: The contour colour is a token, not a constant: near-black (`#1a1a1a`-class) in
  the light scheme, and a light "paper" value in the dark scheme. Every contour — cards, panels,
  map nodes, buttons, inputs, table containers, chips — draws with `border: var(--contour-w)
  solid var(--ink)` where `--contour-w` is 2–3 px.
- **Rationale**: VD-001 makes the outline the primary separator. On the current dark theme a
  near-black outline on a dark panel would vanish, so the contour must flip with the scheme.
  Tokenising it keeps every component rule identical across schemes.
- **Alternatives considered**: (a) *Keep dark outlines in dark mode and lighten panel fills* —
  rejected: forces the dark scheme toward grey cards and loses the saturated dark-field look.
  (b) *Per-component contour colours* — rejected: breaks the single-grammar requirement (FR-002).
  (c) *Drop contours in dark mode, keep shadows* — rejected: violates VD-001; the contour is the
  identity.

## R4 — Depth: hard offset shadows, pressable controls

- **Decision**: Two shadow tokens: `--shadow-rest: 4px 4px 0 var(--ink)` and
  `--shadow-press: 1px 1px 0 var(--ink)`, with a matching `translate(3px, 3px)` on press so the
  control visually moves onto its own shadow. Hover on interactive elements shifts the offset by
  1–2 px or swaps the accent fill; it never adds blur or scale. Cards and overlays carry the
  resting shadow; inline rows (recent turns, table rows) carry a 2–3 px variant so lists do not
  become a wall of heavy shadows.
- **Rationale**: VD-002. A zero-blur offset shadow is the neobrutalist depth cue, and moving the
  offset on press gives the physical, depressible feel the spec asks for — with two token pairs
  and two declarations, no keyframes needed.
- **Alternatives considered**: (a) *Soft blurred shadows for the dark scheme* — rejected:
  violates VD-002 in both schemes; consistency of grammar matters more than dark-mode
  convention. (b) *No shadows, outlines only* — rejected: loses the tactile pressability the spec
  calls for (VD-002 "physically depressible"). (c) *Full drop-shadow filters* — rejected: filter
  rendering is slower on the scrolling map and adds nothing over `box-shadow` here.

## R5 — The eight runtime states as word + three non-hue cues

- **Decision**: Each state keeps its written word (already rendered by `map.js`) and adds three
  non-hue cues from a fixed cue kit — contour weight (2 px vs 3.5 px), dash pattern (solid vs
  `4 3`), and shadow treatment (resting shadow vs none vs doubled offset) — with hue as the
  fourth cue. The mapping (full matrix in `contracts/state-cues.md`): idle = standard contour,
  no shadow; running = 3.5 px contour + accent fill + resting shadow; done = standard contour +
  ok-accent contour colour; skipped/degraded/partial = dashed contour; failed = 3.5 px contour +
  bad-accent contour + doubled shadow; not-reached = reduced opacity (kept) + dashed contour.
- **Rationale**: Spec FR-005 requires word + two non-hue cues; three gives margin under
  forced-colors, where hue is stripped and `border-style`/`border-width`/opacity survive.
  Every cue is a `data-state` attribute selector, so the live player and its tests are
  untouched — the cue layer is purely additive CSS.
- **Alternatives considered**: (a) *Hue plus word only* (current behavior) — rejected: fails
  FR-005 and the grayscale success criterion SC-006. (b) *Icons per state* — rejected: new SVG
  assets inside map nodes clutter a 12 px label row and duplicate what the word says.
  (c) *Animation per state* (pulsing running node) — rejected: VD-007 bans ambient animation and
  it fights reduced-motion.

## R6 — Live lighting on flat fills

- **Decision**: The running highlight swaps the node/edge to a flat accent fill with the heavier
  contour (R5) and, on edges, a wider stroke — no `color-mix` translucency wash, no glow. The
  existing 550 ms play cadence and the `data-state` transitions stay; the transition itself is
  a short (≤150 ms) fill/stroke swap, disabled entirely under reduced motion.
- **Rationale**: VD-003 forbids translucency; the current highlight
  (`color-mix(in srgb, var(--accent) 18%, ...)`) violates the new direction. A flat fill swap is
  *more* visible, not less, which serves SC-007 (identify the working part within 5 s).
- **Alternatives considered**: (a) *Keep the translucent tint* — rejected: violates VD-003.
  (b) *Glow via blurred shadow* — rejected: violates VD-002 and reads as neon, not brutalist.
  (c) *Marching-ants edge animation* — rejected: ambient animation, fails reduced-motion and
  distracts from the status line.

## R7 — Accent and ornament: CSS-only, one per region

- **Decision**: The permitted "sticker" accent (VD-006) is a rotated pseudo-element or a small
  inline-shaped element styled in CSS — e.g. a rotated chip behind the brand word in the sidebar
  and a rotated "LIVE" tag on the live indicator. At most one per region. No image files, no
  icon font, no emoji-as-decoration.
- **Rationale**: Satisfies VD-006's deliberate imbalance while keeping FR-014 (no requests) and
  FR-016 (ornament never over data, never shifts layout — pseudo-elements are absolutely
  positioned inside padded containers).
- **Alternatives considered**: (a) *An SVG logo mark* — rejected: the project deliberately has no
  brand assets (README), and inventing one is out of scope. (b) *Background patterns (dot grids,
  noise)* — rejected: texture violates VD-003 and adds paint cost behind dense tables.
  (c) *Multiple stickers per view* — rejected: VD-006 caps at one; more reads as clutter, not
  character.

## R8 — Verification split: pytest for invariants, quickstart for eyes

- **Decision**: Extend the existing static-asset test family. New tests parse `style.css` as
  text and assert: both scheme blocks define the full token set; the eight `data-state`
  selectors exist with their non-hue declarations; `:focus-visible` rules exist and are not
  clipped by `overflow` on the shell containers; the three media queries exist; no `@import`,
  no `http://`/`https://`, no remote `url()` in any static asset; and the declared contrast
  pairs compute to >= 4.5:1 (3:1 for large text / interactive boundaries) from hex token values
  using the WCAG relative-luminance formula in the test. A parity test diffs the human-readable
  label set rendered by the shell and scripts (nav labels, section heads, button copy) against a
  pinned list. Everything that needs a retina — reflow, grayscale naming, keyboard path, live
  lighting — is a numbered quickstart scenario.
- **Rationale**: The constitution requires the default suite to pass offline; text-level CSS
  assertions plus a computed contrast check are fully deterministic and need no browser. The
  project already tests the shell this way (`test_map_static.py`), so the approach extends a
  proven seam instead of adding a JS runner.
- **Alternatives considered**: (a) *Playwright/Puppeteer visual snapshots* — rejected: browser
  dependency, screenshots are machine-specific, and the constitution's offline-first rule.
  (b) *A CSS parser library* — rejected: new dependency to parse a language the test can scan
  with regexes at this scale. (c) *Manual-only verification* — rejected: FR-012 contrast and
  FR-005 state cues are exactly the kind of invariant that rots without a test.

## R9 — Colour palette

- **Decision**: Light scheme — paper field (`#fdf6e3`-class warm paper), near-black ink, and
  flat saturated accents: yellow `#ffd02f`, blue `#2f6fed`, green `#2fbf71`, red `#ff5a5a`,
  orange `#ff9f1c`. Dark scheme — deep ink field (`#101014`-class), paper-coloured contours,
  the same accents re-valued slightly lighter to hold 4.5:1 against dark fills. Accent roles are
  semantic: yellow = brand/highlight, blue = live/primary action, green = done/ok, red =
  failed/destructive, orange = skipped/degraded/warn. All accent/text pairings are enumerated in
  `contracts/design-tokens.md` and tested per R8.
- **Rationale**: Five accents is the maximum the views need (the current stylesheet already uses
  four semantic hues); more would dilute the grammar. Warm paper rather than pure white keeps
  the poster feel without dropping contrast.
- **Alternatives considered**: (a) *A larger 8–10 colour palette* — rejected: VD-003 uses colour
  to mark sections and states; too many hues destroy that signalling. (b) *Neon/high-chroma
  palette* — rejected: fails AA on both fields without large-area-only usage, which fights the
  data-first requirement. (c) *Monochrome with one accent* — rejected: the eight states need
  semantic hue as their fourth cue.

## Resolved Technical Context fields

- **Testing** — resolved by R8 (pytest text/assertion tests + quickstart; no JS runner).
- **Primary Dependencies** — resolved by R1/R2: none added; fonts are system stacks.
- **Constraints** — resolved by R1/R2/R7: no external request, no build step, no binary asset.
- **Performance Goals** — resolved by R4/R6: static single file, attribute-state transitions
  only, no keyframe animation on the map; transitions ≤150 ms, removed under reduced motion.
- No other field was open: language, storage, platform, project type and scale were fixed by the
  repository and the spec.
