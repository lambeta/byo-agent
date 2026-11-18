---

description: "Task list for byo logo & wordmark implementation"
---

# Tasks: byo Logo & Wordmark

**Input**: Design documents from `/specs/005-byo-logo-design/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/brand-assets.md, quickstart.md

**Tests**: Included — plan.md §"Test mapping" and contracts/brand-assets.md §6 define deterministic
offline tests per contract clause. Write tests FIRST per story and watch them FAIL before implementing.

**Organization**: Tasks grouped by user story (US1 header, US2 surfaces, US3 maintainability).

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Brand source zone and authoring tooling (no runtime dependency).

- [X] T001 Create directories `brand/` (repo root, sources) and `byo/ops/static/brand/` (served)
- [X] T002 [P] Download Zilla Slab Bold (`brand/ZillaSlab-Bold.ttf`) and its SIL OFL 1.1 text (`brand/OFL.txt`) from google/fonts; verify the licence file names "SIL OPEN FONT LICENSE Version 1.1"
- [X] T003 [P] Install `fonttools` into the dev venv (authoring tool only — do NOT add to pyproject runtime deps) and write `brand/outline.py`: reads the font, emits SVG `<path>` d-strings for given letters with advance-width composition

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The logo master and its served variants — every user story consumes these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Author `brand/master-wordmark.svg`: "byo" lowercase in Zilla Slab Bold as outlined paths (via `brand/outline.py`), on the theme's yellow sticker with ink contour, hard offset shadow, and the signature slight (-2deg) tilt; commented, human-readable XML; colours limited to { #ffd02f, #1a1a1a, #ffffff }
- [X] T005 Derive `byo/ops/static/brand/wordmark.svg` from the master: self-contained sticker (baked colours, no CSS vars), explicit viewBox, no width/height attributes, < 10 KB, no `<text>`/`<image>`/`<script>`/external refs
- [X] T006 Derive `byo/ops/static/brand/mark.svg` from the master: square viewBox compact mark — yellow sticker square + ink contour + single Zilla Slab Bold "b" — legible at 16 px, same structural rules as T005

**Checkpoint**: `brand/` and `byo/ops/static/brand/` complete; variants trace to master

---

## Phase 3: User Story 1 - Open the dashboard and see a product, not a label (Priority: P1) 🎯 MVP

**Goal**: The dashboard sidebar header shows the new inline wordmark (theme-token-driven), replacing the Archivo Black text sticker, with zero layout shift.

**Independent Test**: `uv run byo dashboard` → header shows new wordmark; `make eval` brand tests green; old `brand-sticker` gone.

### Tests for User Story 1 ⚠️ (write FIRST, must FAIL)

- [X] T007 [P] [US1] Create `evals/deterministic/test_brand_assets.py` with header tests (contracts §3.1–3.2): `test_header_inline_svg_accessible_and_themed` — `index.html` `.brand` contains inline `<svg role="img" aria-label="byo">`; inline SVG uses only `currentColor`/`var(--byo-*)` paint references (no hex literals)
- [X] T008 [P] [US1] Add remnant test to `evals/deterministic/test_brand_assets.py` (contracts §3.5): no `brand-sticker` class/rule remains in `index.html` or `style.css`

### Implementation for User Story 1

- [X] T009 [US1] Replace `<span class="brand"><span class="brand-sticker">byo</span></span>` with the inline wordmark SVG (paths from master, fills via `var(--byo-accent-brand)` sticker / `var(--byo-ink)` letters+contour / `var(--byo-ink)` shadow) in `byo/ops/static/index.html`
- [X] T010 [US1] Rewrite `.brand` rules and delete `.brand-sticker` rules in `byo/ops/static/style.css`: size the inline SVG to the current header box (24 px cap height), keep rail layout/keyboard order unchanged (no reflow)
- [X] T011 [US1] Manual pass per quickstart §2–3: header legible in light + dark, repaint on toggle, narrow-window no-overflow

**Checkpoint**: US1 shippable alone (MVP)

---

## Phase 4: User Story 2 - The logo survives every theme, size and surface (Priority: P2)

**Goal**: Favicon, collapsed-rail compact mark, and README header all show the same logo system.

**Independent Test**: tab icon renders; collapse rail shows the mark; README preview shows the wordmark.

### Tests for User Story 2 ⚠️ (write FIRST, must FAIL)

- [X] T012 [P] [US2] Extend `evals/deterministic/test_brand_assets.py` with `test_served_svgs_are_self_contained` + `test_mark_is_square_and_simple` (contracts §2.1–2.5: XML parse, viewBox, path-only, allowed hex set, square mark, < 10 KB)
- [X] T013 [P] [US2] Extend `evals/deterministic/test_brand_assets.py` with `test_favicon_and_rail_and_no_sticker_remnants` (§3.3–3.4: favicon link in `<head>`; collapsed-rail mark wiring in index.html + style.css) and `test_brand_assets_served` (§4: GET `/static/brand/wordmark.svg` + `/static/brand/mark.svg` → 200 `image/svg+xml`, following the pattern in `evals/deterministic/test_dashboard.py`)

### Implementation for User Story 2

- [X] T014 [US2] Add `<link rel="icon" type="image/svg+xml" href="/static/brand/mark.svg">` to `byo/ops/static/index.html` `<head>`
- [X] T015 [US2] Collapsed rail: add compact-mark `<img src="/static/brand/mark.svg" alt="byo">` in the `.brand` slot in `byo/ops/static/index.html`; in `byo/ops/static/style.css` swap wordmark→mark under `body.rail-collapsed` (brand no longer hidden)
- [X] T016 [US2] Show the wordmark in the `README.md` header via relative path `byo/ops/static/brand/wordmark.svg`
- [X] T017 [US2] Manual pass per quickstart §3–4: tab icon at 16 px, collapsed rail, README preview, squint test at both size extremes

**Checkpoint**: US1 + US2 both independently verifiable

---

## Phase 5: User Story 3 - The logo is a maintainable in-repo asset (Priority: P3)

**Goal**: Sources readable, licence recorded, derivation documented and repeatable.

**Independent Test**: fresh-clone maintainer reads `brand/README.md`, re-derives a variant, tests stay green.

### Tests for User Story 3 ⚠️ (write FIRST, must FAIL)

- [X] T018 [P] [US3] Extend `evals/deterministic/test_brand_assets.py` with `test_licence_and_design_note_present` + `test_readme_references_wordmark` (contracts §5: OFL.txt names SIL OFL 1.1; `brand/README.md` states typeface + derivation + rejected alternatives; README.md references the wordmark path)

### Implementation for User Story 3

- [X] T019 [US3] Write `brand/README.md` design note: mechanism (outlined Zilla Slab Bold on theme sticker), typeface + licence record, regeneration steps (`brand/outline.py` usage), rejected alternatives (runtime @font-face webfont, `<img>` header, single-zone assets) per constitution documentation duty
- [X] T020 [US3] Verify derivation: re-run the documented regeneration from `brand/master-wordmark.svg` and confirm the served variants match (no hand-drift)

**Checkpoint**: All three stories independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T021 Run `make eval` and `make gate` fully offline — all green, including pre-existing style/dashboard suites
- [X] T022 Walk `specs/005-byo-logo-design/quickstart.md` §1–5 end-to-end; fix any failure signals found
- [X] T023 Verify wheel packaging still includes `byo/ops/static/brand/*.svg` (hatchling packages = ["byo"] picks up package data; confirm with a build or file check)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none — start immediately. T002 ∥ T003 (different files).
- **Foundational (Phase 2)**: needs T002+T003 (font + tooling). T005, T006 depend on T004 (master). BLOCKS all stories.
- **US1 / US2 / US3 (Phases 3–5)**: sequential in priority order here (single operator); tests before implementation within each story.
- **Polish (Phase 6)**: after all stories.

### Parallel Opportunities

- T002 ∥ T003 (font fetch ∥ tooling script)
- T007 ∥ T008 (two independent test additions, same file — append sequentially in one edit each)
- T005 ∥ T006 (different output files, both from master)

## Parallel Example: Phase 1

```bash
Task: "Download Zilla Slab Bold + OFL.txt into brand/"
Task: "Install fonttools in venv and write brand/outline.py"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

Setup → Foundational → US1 → validate dashboard header → shippable increment.

### Incremental Delivery

US1 (header) → US2 (favicon/rail/README) → US3 (design note + regeneration) → Polish (make eval + quickstart).
