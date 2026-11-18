# Feature Specification: byo Logo & Wordmark

**Feature Branch**: `005-byo-logo-design`

**Created**: 2026-11-19

**Status**: Draft

**Input**: User description: "设计一个符合产品定位和现有主题的logo，产品名 byo 你要换字体"

**Product context**: byo is "a small, local-first agent you can read in an afternoon" — built, not
configured; every mechanism visible in source. Its dashboard (specs/003-neobrutalist-dashboard)
speaks a deliberate neobrutalist language: heavy dark contours, flat saturated colour blocks, hard
offset shadows, bold display type, tracked uppercase labels. Today the product has no logo: the
dashboard header shows the word "byo" as plain text on a yellow sticker, set in the dashboard's own
display font. This feature gives the product a real, distinctive mark — with a typeface of its own,
not the display font it currently borrows.

**Depends on**: `specs/003-neobrutalist-dashboard` — the theme tokens (ink, field, brand yellow,
contour widths, shadow geometry) and the sidebar brand slot this logo occupies already exist there.
This feature adds brand assets and replaces that header sticker; it changes no theme tokens and no
dashboard behaviour.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open the dashboard and see a product, not a label (Priority: P1)

A person starts the local dashboard and lands on any view. Where a plain text sticker used to sit,
there is now a designed "byo" logo: a wordmark with its own typographic character, visibly different
from the dashboard's display font, and unmistakably at home in the neobrutalist theme — heavy
contours, flat colour, hard offset shadow. It reads as the product's name at a glance and as the
product's personality on a second look: built by hand, legible, a little defiant.

**Why this priority**: The header brand slot is the one place every user sees the product name on
every visit. The font change the user explicitly asked for lives or dies here. If the wordmark only
exists as files on disk but the dashboard still shows the old sticker, the feature has not shipped.

**Independent Test**: Open the dashboard against any recorded sample. The header shows the new logo
instead of the old text sticker; the product name "byo" is still the most legible element in the
sidebar; the surrounding navigation, status pill and view content are unchanged.

**Acceptance Scenarios**:

1. **Given** the dashboard loads, **When** any view appears, **Then** the sidebar header shows the new logo, the word "byo" is immediately readable, and no trace of the old plain-text sticker rendering remains.
2. **Given** a viewer familiar with the previous dashboard, **When** they compare old and new headers, **Then** the wordmark's typeface is recognisably different from the dashboard's display font (the previously used heavy grotesque) without being told so.
3. **Given** the new logo in place, **When** a viewer scans the header, **Then** the logo shares the theme's visual vocabulary (contour, flat fill, hard shadow, theme colours) and does not look pasted-in from another product.
4. **Given** the person collapses the sidebar rail, **When** the header compacts, **Then** the brand presence degrades gracefully — either a compact mark remains or the slot empties cleanly, with no clipped or half-rendered artwork.

---

### User Story 2 - The logo survives every theme, size and surface (Priority: P2)

The same person switches between light and dark schemes, glances at the browser tab, and opens the
project README. The logo keeps its identity in both schemes, stays recognisable at favicon scale,
and appears as the same mark everywhere the product name is shown — no surface keeps a stale or
improvised rendering.

**Why this priority**: A logo that only works in one scheme at one size is a screenshot, not a brand
asset. But a beautiful mark that is never reused beyond the dashboard still delivers the core value,
so this ranks below P1.

**Independent Test**: Toggle light and dark schemes and inspect the header in both; check the browser
tab icon; open the README header. All show the same logo system, each legible in its context.

**Acceptance Scenarios**:

1. **Given** the light scheme, **When** the person switches to dark, **Then** the logo repaints with scheme-appropriate colours, keeps at least the theme's standard contrast, and loses no contour or shadow definition.
2. **Given** the browser tab, **When** it renders at its smallest size, **Then** the mark is still identifiable as "byo" rather than an abstract blob (a compact variant is acceptable here).
3. **Given** the project README viewed in a repository browser, **When** its header renders, **Then** it shows the same logo as the dashboard, in the same colours where the medium allows.
4. **Given** the dashboard opened with no network connection, **When** the page loads, **Then** the logo renders fully — every asset it needs is local.

---

### User Story 3 - The logo is a maintainable in-repo asset, not a magic file (Priority: P3)

A maintainer wants to recolour the logo for a future theme tweak, or regenerate a small variant.
The logo's sources live in the repository in a form a person can read and edit with ordinary tools,
its typeface is licensed for bundling, and its variants are produced from one master rather than
hand-drawn copies that drift apart.

**Why this priority**: The project's whole identity is "readable in an afternoon" — a binary blob
or an unbundlable font would contradict the positioning the logo is meant to express. This is
sustaining value, so it ranks below first impression and coverage.

**Independent Test**: Clone the repository fresh, read the logo source, change one colour, rebuild
or re-export the variants, and confirm every surface reflects the change with no other file edited.

**Acceptance Scenarios**:

1. **Given** a fresh clone, **When** a maintainer inspects the logo sources, **Then** they are human-readable text and their relationship (master → variants) is documented in a short note.
2. **Given** the chosen typeface, **When** its licence is reviewed, **Then** it permits bundling and embedding in this open-source project, and the licence is recorded alongside the asset.
3. **Given** any shipped variant (header, compact mark, favicon, README), **When** its source is traced, **Then** it derives from the single master logo, not from a hand-edited duplicate.

---

### Edge Cases

- What happens at extremely small sizes (16 px tab icon, collapsed rail)? The full wordmark may
  degrade to an unreadable smudge — a compact variant must take over.
- What happens in forced-colours / high-contrast mode? Decorative fills may be overridden by the
  operating system; the name must still read as text, not vanish into the background.
- What happens if the logo font fails to load or is removed? The header must fall back to a
  readable system rendering of "byo", never to blank space.
- What happens on monochrome contexts (print, terminal, single-colour embroidery)? A one-colour
  variant should survive with the wordmark still legible.
- What happens when the sidebar is at its narrowest width or the window is very small? The logo
  must not overflow, wrap mid-word, or push navigation out of place.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The product MUST have a designed logo whose primary form is the "byo" wordmark,
  used as the single canonical rendering of the product name on branded surfaces.
- **FR-002**: The wordmark MUST be set in a typeface that is visibly distinct from the dashboard's
  current display font ("Archivo Black"). Using the existing display font — or a lookalike of it —
  for the logo does not satisfy this feature; the user explicitly asked for a font change.
- **FR-003**: The logo MUST be visually coherent with the existing neobrutalist theme: it consumes
  the established brand vocabulary (heavy contours, flat saturated fills, hard offset shadows, the
  brand yellow and ink tones) and introduces no colour or treatment that contradicts it.
- **FR-004**: The logo MUST be supplied in variants fit for their contexts — at minimum the full
  wordmark for the header and documentation, and a compact mark for small square contexts (tab
  icon, collapsed rail) — all derived from one master source.
- **FR-005**: The logo MUST render correctly in both the light and dark dashboard schemes, with
  contrast at least equal to the theme's standard for brand elements, and must respect
  forced-colours mode by remaining legible as text.
- **FR-006**: The dashboard header MUST display the new logo in place of the current text sticker,
  in all views, with no layout shift, no overflow at small window widths, and no loss of any
  existing header information or behaviour.
- **FR-007**: Every asset the logo needs MUST be stored in the repository and served locally;
  rendering the logo MUST require zero network requests, consistent with the product's local-first
  positioning and offline-first testing rule.
- **FR-008**: The chosen typeface MUST carry a licence that permits bundling and embedding in this
  open-source project, and that licence MUST be recorded in the repository next to the asset.
- **FR-009**: Logo master sources MUST be human-readable text files, reviewable in ordinary diffs
  and editable without proprietary tools, honouring the project's "read it in an afternoon"
  positioning.
- **FR-010**: The project README header MUST show the new logo, replacing any plain-text title
  treatment, so the first public surface of the repository matches the product.

### Key Entities

- **Logo (master)**: the single source design of the "byo" mark; attributes: typeface, letterform
  geometry, colour usage, contour/shadow treatment, clear-space and minimum-size rules.
- **Variant**: a context-fit rendering derived from the master (full wordmark, compact mark, tab
  icon, mono/one-colour version); attributes: target surface, size range, colour scheme.
- **Surface**: a place the logo appears: dashboard header, browser tab icon, project README.
  Terminal output stays plain text and is explicitly not a surface.
- **Typeface licence**: the legal record permitting the font's use and bundling; attached to the
  logo sources.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time viewer can read the product name "byo" from the logo at header size
  within one glance, in both light and dark schemes (verified with 5/5 viewers in an informal
  recognition check).
- **SC-002**: In a side-by-side of the old header and the new header, 5/5 reviewers identify the
  wordmark as a different typeface without prompting, and at least 4/5 judge it consistent with the
  dashboard's visual theme.
- **SC-003**: The logo is recognisable as "byo" at every shipped size, from the 16 px tab icon to
  the full README header, using the designated variant for each size.
- **SC-004**: The dashboard renders the complete logo with zero network requests and zero layout
  shift relative to the previous header on first paint.
- **SC-005**: Logo-to-background contrast meets the theme's existing brand-element contrast
  (at least 3:1 for its size class) in both schemes and remains legible in forced-colours mode.
- **SC-006**: Every surface that displays the product name uses the new logo system — no shipped
  surface retains the old text-sticker rendering or an improvised substitute.

## Assumptions

- Scope is limited to the dashboard header, the browser tab icon, and the README header. The
  terminal chat and trajectory renderer keep plain text; packaging icons, social preview images
  and a public website are out of scope for this feature.
- The exact typeface is selected during planning/design against the criteria in FR-002, FR-003,
  FR-007 and FR-008 (distinct from the current display font, tonally coherent with neobrutalism,
  bundleable licence, locally servable). The user delegated the choice with "你要换字体".
- The wordmark is the primary deliverable; the compact mark is a derived simplification, not a
  second independent design.
- Existing theme tokens remain the single source of truth for colour, contour and shadow; the logo
  adds no parallel palette.
- The logo is authored in-repo by the maintainer/agent (no external design vendor), and the
  deliverable is considered shipped only when the dashboard actually renders it.
