# Implementation Plan: Neobrutalist Dashboard Refresh

**Branch**: `003-neobrutalist-dashboard` | **Date**: 2026-11-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-neobrutalist-dashboard/spec.md`

## Summary

Restyle the local dashboard — sidebar, composer, all five views, the runtime map, the turn-detail
and raw-record overlays, and the empty/loading/error states — into a self-contained Neobrutalist
visual language: thick dark contours, hard offset shadows with no blur, flat saturated colour
blocks, bold display type, near-sharp corners and restrained asymmetric accents. Both the light
and dark appearance schemes follow the operating system and keep WCAG 2.1 AA contrast.

The implementation is presentation-only: one rewritten stylesheet driven by a small set of design
tokens (CSS custom properties), with structural HTML or script changes allowed only where a style
cannot be expressed otherwise (an extra wrapper, a class name, an inline SVG accent). No route,
payload, label, count or keyboard shortcut changes; no new runtime dependency, no webfont
download, no build step. The existing deterministic suite keeps passing, and new static-asset
tests pin the token, state-cue and no-external-request invariants.

## Technical Context

**Language/Version**: Python >= 3.11 (repository floor) for the server and tests; the dashboard
itself is plain HTML, CSS and classic `<script>` JavaScript — no transpilation target, so the
CSS is written to current Chrome, Safari, Firefox and Edge (per spec Assumptions).

**Primary Dependencies**: none added. The four runtime dependencies (`anthropic`, `openai`,
`python-dotenv`, `rich`) and the `pytest`/`ruff` dev extras stay unchanged. No CSS
framework, preprocessor, icon set, font package or utility library is introduced.

**Storage**: N/A. The feature reads and changes no data; `state.db`, the trajectory files and
every API payload are untouched.

**Testing**: `pytest` under `evals/deterministic/`. New tests assert stylesheet-level facts
that can be checked without a browser: token definitions for both schemes, the eight state-cue
selectors, focus-visible treatment, the three media queries (`prefers-color-scheme`,
`prefers-reduced-motion`, `forced-colors`), absence of external URLs (`http(s)://`,
`@import`, `url(` to remote hosts) in every static asset, and content parity of the HTML shell
and script-rendered labels. Visual verification (contrast sampling, keyboard path, reflow at
1280/900/375, grayscale state naming, live lighting on new fills) is the `quickstart.md`
checklist — this project has no JS test runner and this feature does not add one.

**Target Platform**: macOS 13+ and Linux, one local user, `127.0.0.1` only. The browser is the
rendering target: current Chrome, Safari, Firefox and Edge.

**Project Type**: single project — an installable Python package serving a plain static web UI.
The change lives entirely in `byo/ops/static/` plus its tests.

**Performance Goals**: first view renders in under 1 s locally (spec SC-009); keystroke-to-echo
stays under 100 ms while a turn streams; the stylesheet stays a single static file served with
the same caching behavior as today; no added network request; live lighting remains a state
attribute change, not a layout-thrashing animation.

**Constraints**: no new runtime dependency; no build step or package manager for the front end;
no external request for fonts, images or styles (spec FR-014); no change to API contracts, route
set, copy or information architecture (spec FR-015); WCAG 2.1 AA contrast in both schemes (spec
FR-012); reduced-motion and forced-colors honored; the map's own scroll region stays the only
intentional horizontal scroll (spec FR-010); the offline deterministic suite must keep passing
with no network and no credentials.

**Scale/Scope**: one stylesheet (~250 lines before, expected ~450–550 after), one HTML shell,
seven classic scripts, five views, four overlays, eight runtime states, three system states, two
appearance schemes, three reference widths (1280/900/375). No new endpoint, event type, store or
configuration knob.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Evidence |
|---|---|---|
| I. Build From Primitives | PASS | The visual language is authored in this repository as one stylesheet and, where unavoidable, small markup hooks in the existing shell and scripts. No CSS framework, theme package or design system dependency is added; a reviewer can read every rule that produces the look. The stylesheet header carries the design note: the mechanism (token-driven flat design) and the rejected alternatives (a utility framework, a component library, a prebuilt theme). |
| II. Provider-Agnostic Model Boundary | PASS | Nothing under `byo/loop/` changes. The dashboard never branches on a provider today and the restyle adds no such branch. |
| III. Small Modules With Narrow Contracts | PASS | The stylesheet remains one module with a documented token seam (`contracts/design-tokens.md`). The eight runtime states keep a single vocabulary owned by the map and card renderers; the cue mapping is a contract (`contracts/state-cues.md`) rather than scattered ad-hoc rules. Any markup hook added to a script is named in the coverage contract (`contracts/surface-parity.md`). |
| IV. Observable by Default | PASS | The trajectory, event feed, raw record and redaction are untouched; the refresh only changes how existing records are drawn. The map's text alternative and the status live region are preserved by contract and tested. |
| V. Eval-Driven Behavior Change (NON-NEGOTIABLE) | PASS | No prompt, tool description, loop logic, context strategy or memory policy changes, so no behavior baseline can move. The change still adds measurement: deterministic static-asset tests pin the new invariants (tokens, state cues, media queries, no external requests, content parity), and the existing suite including `test_map_static.py` and `test_api_contract.py` must keep passing unchanged. |

**Additional constraints check**: dependency count unchanged; no front-end build step; default
test path runs offline with no credentials; loopback bind unchanged; no secret or credential is
rendered differently — redaction stays at the sink and the key field stays a password input; no
brand asset, font file or illustration is copied from any other product; display typography comes
from locally available system faces, so no font is downloaded at runtime and no binary asset is
added to the repository.

No violations.

## Project Structure

### Documentation (this feature)

```text
specs/003-neobrutalist-dashboard/
├── plan.md              # this file
├── research.md          # Phase 0: styling decisions, rationale, rejected alternatives
├── data-model.md        # Phase 1: design-token model, component inventory, state-cue matrix
├── quickstart.md        # Phase 1: runnable visual validation scenarios
├── contracts/
│   ├── design-tokens.md # token names, light/dark values, contrast pairs, invariants
│   ├── state-cues.md    # 8 runtime states × non-hue cues; focus/hover/pressed contract
│   └── surface-parity.md# surface inventory, required treatments, content-parity checklist
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # Phase 2 output (/speckit-tasks), not created here
```

### Source Code (repository root)

```text
byo/
├── ops/
│   ├── dashboard.py              # unchanged: routes, payloads, static serving
│   ├── map.py                    # unchanged: graph, event map, summaries
│   ├── turn_detail.py            # unchanged
│   └── static/
│       ├── index.html            # [modified] token-bearing root, at most one accent element, font-stack note
│       ├── style.css             # [rewritten] tokens, contours, hard shadows, states, both schemes, motion guards
│       └── js/
│           ├── render.js         # [modified only if a style needs a hook] e.g. user-card class already exists
│           ├── map.js            # [modified only if a style needs a hook] node markup unchanged by default
│           ├── live.js           # unchanged: state vocabulary drives the cues
│           ├── api.js            # unchanged
│           ├── observe.js        # unchanged
│           ├── dock.js           # unchanged
│           └── main.js           # unchanged

evals/
├── deterministic/
│   ├── test_map_static.py        # [extended] stylesheet invariants join the existing shell checks
│   ├── test_style_tokens.py      # [new] tokens defined for both schemes; contrast pairs declared
│   ├── test_style_states.py      # [new] 8 state selectors, focus-visible, 3 media queries present
│   └── test_style_offline.py     # [new] no external URL/@import/remote url() in any static asset
└── fixtures/                     # unchanged
```

**Structure Decision**: single project, and inside it a single stylesheet. The whole identity is
expressed as design tokens at the root plus component rules, so both appearance schemes are the
same token set re-valued — there is no second stylesheet to drift. Script files change only where
a visual requirement cannot be met from CSS alone (for example a wrapper for an offset sticker or
a class that distinguishes a primary action); every such hook is enumerated in
`contracts/surface-parity.md` so the parity audit can check it. Keeping everything in
`style.css` also keeps the "read the product in an afternoon" promise intact.

## Complexity Tracking

None. One stylesheet and a token block are the simplest thing that can hold a whole visual
language; a framework, a second stylesheet per scheme or a theme switcher would each add a layer
the spec forbids or does not need.

## Phase 0: Outline & Research

Complete — see [research.md](research.md). Every Technical Context field is resolved; no
clarification remains. The decisions that shape the design are:

- **R1 Token-driven single stylesheet** — one `:root` token set, re-valued under
  `prefers-color-scheme`, rather than two stylesheets or a runtime theme switch.
- **R2 System display faces** — bold locally available grotesques via a curated system stack
  instead of a bundled or downloaded webfont, satisfying the offline constraint with zero assets.
- **R3 Contour as a token** — the outline is a color token (`--ink`) that flips with the scheme,
  so contours stay visible on dark fills instead of disappearing.
- **R4 Hard shadow as depth** — a single solid offset `box-shadow` token pair (resting, pressed)
  gives the depressible feel; hover never lifts, it shifts the offset.
- **R5 Non-hue state cues** — the eight runtime states are encoded as word + border weight +
  dash pattern + shadow treatment, with hue as the fourth cue, so grayscale and forced-colors
  keep working.
- **R6 Live lighting on flat fills** — the running state swaps a node's fill to a flat accent
  block with a heavier contour rather than a translucent glow, so the style's no-translucency
  rule survives the animation.
- **R7 CSS-only accents** — the one permitted sticker accent per region is pure CSS (a rotated
  pseudo-element or inline SVG data-free element), never an image request.
- **R8 Test what can be tested without a browser** — token presence, state selectors, media
  queries, external-request absence and label parity in pytest; eyes-on checks in quickstart.

## Phase 1: Design & Contracts

Complete — the artifacts below are generated beside this plan:

- [data-model.md](data-model.md) — the design-token model (fields, schemes, derived pairs), the
  component inventory, the state-cue matrix and validation rules drawn from the spec.
- [contracts/design-tokens.md](contracts/design-tokens.md) — every token, its light and dark
  value, the contrast pairs a test enforces, and the change rules for the token seam.
- [contracts/state-cues.md](contracts/state-cues.md) — the eight runtime states mapped to word +
  non-hue cues, the focus/hover/pressed contract, and the reduced-motion and forced-colors
  fallbacks.
- [contracts/surface-parity.md](contracts/surface-parity.md) — the surface inventory (5 views,
  sidebar, composer, 4 overlays, 3 system states), the required treatment per surface, every
  permitted markup hook, and the content-parity checklist of labels, counts and actions.
- [quickstart.md](quickstart.md) — runnable scenarios: serve the dashboard, walk all five views
  in both schemes, run a live turn, keyboard-only path, reflow at three widths, grayscale state
  naming, 200% zoom, offline render, and the edge-case sweep.

No API contract changes and no data migration are generated, because none exist: every route,
payload and file stays byte-compatible with the current dashboard.

## Constitution Check (post-design)

Re-evaluated against the artifacts above. Verdicts unchanged: I–V all PASS.

- The identity is one authored stylesheet plus enumerated markup hooks; no framework or theme
  dependency entered the design.
- The token seam is the only public surface; component rules consume tokens, and the contract
  names the allowed change procedure.
- The state vocabulary stays owned by the existing renderers; cues are additive styling over the
  same `data-state` attributes, so the live player and map tests are untouched.
- Offline render is a hard contract (no external URLs in any static asset) with a test, keeping
  the default suite network-free.
- Content parity is enumerated label-by-label, so the "no information lost" requirement is
  checkable rather than aspirational.

## Risks and Sequencing Notes

- **Highest risk: map legibility on flat saturated fills.** The live highlight must read against
  the new node fills without translucency. Mitigation: R6 (fill swap + heavier contour), the
  state-cue contract's non-hue cues, and the quickstart's live-turn and grayscale checks before
  any polish pass.
- **Second: contrast regression in the dark scheme.** Saturated accents on dark fields fail AA
  easily. Mitigation: the token contract declares light and dark values per accent with the
  paired text token, and `test_style_tokens.py` checks every declared pair computes to >= 4.5:1
  (large text 3:1) from the hex values.
- **Third: hard shadows causing clipped focus or overflow.** Offset shadows can overflow their
  container and get clipped by `overflow: hidden` ancestors, and focus rings can clip on the
  scrollport edge. Mitigation: padding allowance in the coverage contract, the quickstart
  keyboard path on every view, and the reflow checks at 900 and 375.
- **Fourth: scope creep into structure.** A restyle tempts markup "improvements" that break
  parity. Mitigation: markup hooks are an enumerated allowlist in `surface-parity.md`; anything
  else is out of bounds, and the parity test diffs rendered labels against the pre-change list.
- **Sequencing**: tokens and shell first (sidebar, composer), then the map (highest risk), then
  cards and timeline, then tables and forms, then the edge-case and accessibility sweep. The
  quickstart runs after each slice, not only at the end.
