# Implementation Plan: byo Logo & Wordmark

**Branch**: `005-byo-logo-design` | **Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-byo-logo-design/spec.md`

## Summary

Give byo a real logo: a "byo" wordmark set in **Zilla Slab Bold** (slab serif, SIL OFL 1.1) —
visibly distinct from the dashboard's Archivo Black display font, as the user explicitly required —
drawn onto the theme's signature yellow sticker with ink contour and hard offset shadow. The
runtime rendering is **outlined SVG paths, not live text**: the header carries an inline SVG that
consumes the existing `--byo-*` tokens (correct in both schemes, zero requests, zero layout
shift), while two self-contained served SVGs cover the README header and the favicon/collapsed-rail
compact mark. Source assets and the vendored font live at repo-root `brand/` (not served), keeping
the served static tree text-only so the existing offline-asset tests keep passing. One new
deterministic pytest module asserts the brand-asset contract offline; visual verification follows
the quickstart checklist.

## Technical Context

**Language/Version**: Python 3.11+ (server, tests); hand-authored SVG / CSS / HTML (assets, no build step)

**Primary Dependencies**: None added at runtime. Authoring-time assets: Zilla Slab Bold (SIL OFL 1.1,
vendored with licence) and fonttools (dev-venv only, not in pyproject). Dashboard serving stays stdlib `ThreadingHTTPServer`.

**Storage**: Files only — SVG assets in `byo/ops/static/brand/`, sources in repo-root `brand/`. No DB change.

**Testing**: pytest, `evals/deterministic/test_brand_assets.py` (new), offline, no network/credentials.
Existing `test_style_offline.py`, `test_style_tokens.py`, `test_style_parity.py` must stay green.

**Target Platform**: Local dashboard in modern browsers (light + dark `data-theme`), browser tab
icon, README rendered by GitHub/m markdown viewers.

**Project Type**: CLI + local web dashboard (existing); this feature is brand assets + dashboard integration.

**Performance Goals**: Header logo adds zero network requests (inline SVG); favicon is one request
under 10 KB; no cumulative layout shift versus the current header on first paint.

**Constraints**: Offline-capable (zero external references in any served asset); no front-end build
step; no new runtime dependency; served static tree stays text-only (binary font must NOT live under
`byo/ops/static/` — `test_style_offline.py` reads every served file as UTF-8); logo letterforms are
outlined paths (no `<text>`, no `@font-face` at runtime); theme via existing `--byo-*` tokens only.

**Scale/Scope**: 1 inline header SVG, 2 served SVGs (wordmark, compact mark), 1 vendored font +
licence, 3 surfaces (dashboard header, favicon, README), 1 new test module, 1 design note.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict | Evidence |
|------|---------|----------|
| I. Build From Primitives | PASS | Logo is hand-authored SVG source in this repo; no icon library, design SaaS, or asset pipeline owns any part of it. Master → variant derivation documented in `brand/README.md`. |
| II. Provider-Agnostic Model Boundary | PASS (N/A) | No model involvement; nothing touches the adapter seam. |
| III. Small Modules With Narrow Contracts | PASS | No new module: assets live in the existing static tree; the only new "contract" is the brand-asset contract documented in `contracts/brand-assets.md` and asserted by one focused test file. |
| IV. Observable by Default | PASS (N/A) | Static assets emit no events; no runtime behaviour changes, so the trace surface is untouched. |
| V. Eval-Driven Behavior Change | PASS | No prompt/loop/memory change. Visual change is gated by new deterministic tests (asset structure, integration, offline) plus a manual quickstart checklist; old-vs-new header comparison is part of review. |
| Dependency budget | PASS (justified) | Zero new runtime dependencies. The vendored font is an authoring-time asset (not imported, not served, not loaded at runtime — letterforms ship as outlined paths); justification recorded here and in `brand/README.md`. |
| Offline-first testing | PASS | New tests are pure filesystem assertions; manual checks need no network. |
| Documentation duty | PASS | `brand/README.md` carries the design note: mechanism, typeface choice, regeneration steps, and rejected alternatives. |

**Post-Phase-1 re-check**: unchanged — the design adds no module, dependency, or runtime behaviour.

## Project Structure

### Documentation (this feature)

```text
specs/005-byo-logo-design/
├── plan.md              # This file
├── research.md          # Phase 0: typeface + rendering-strategy decisions
├── data-model.md        # Phase 1: logo/variant/surface/licence entities
├── contracts/
│   └── brand-assets.md  # Phase 1: asset inventory + SVG structural contract
├── quickstart.md        # Phase 1: end-to-end validation guide
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
brand/                            # NEW — source assets (NOT served, NOT packaged)
├── README.md                     # design note: mechanism, typeface, regeneration, rejected alternatives
├── master-wordmark.svg           # editable master with comments/guides
├── ZillaSlab-Bold.ttf            # authoring source (Zilla Slab Bold; not served, not loaded at runtime)
└── OFL.txt                       # SIL Open Font License 1.1 (FR-008 record)

byo/ops/static/
├── index.html                    # EDIT — inline wordmark SVG in .brand slot; favicon <link>; rail mark
├── style.css                     # EDIT — .brand becomes inline-SVG sizing; collapsed rail shows mark
└── brand/                        # NEW — served, text-only
    ├── wordmark.svg              # full wordmark, self-contained sticker (README + reference)
    └── mark.svg                  # compact square mark (favicon + collapsed rail)

evals/deterministic/
└── test_brand_assets.py          # NEW — offline contract tests for all of the above

README.md                         # EDIT — header shows wordmark.svg
```

**Structure Decision**: Two-zone layout. Repo-root `brand/` holds authoring sources (master SVG,
font, licence, design note) — deliberately outside `byo/ops/static/` so the served tree stays
text-only and the wheel package stays free of binaries; `byo/ops/static/brand/` holds only the
derived, served SVGs. The header logo is an inline SVG in `index.html` (not an `<img>`) because
only inline markup can consume the page's `--byo-*` theme tokens under the manual
`data-theme` switch; the served SVGs are self-contained stickers that render identically
regardless of host scheme, which is what README and favicon contexts require.

## Complexity Tracking

No constitution violations; nothing to justify.
