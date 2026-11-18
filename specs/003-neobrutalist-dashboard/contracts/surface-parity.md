# Contract: Surface Coverage and Content Parity

**Date**: 2026-11-18 | **Plan**: [../plan.md](../plan.md)

Two checklists in one contract: every surface that must carry the new language (spec FR-001,
SC-001), and every piece of content that must survive the restyle (spec FR-015, SC-002). The
parity list is pinned from the current renderers; a test diffs rendered labels against it.

## Surface inventory (12 surfaces)

| # | Surface | Components and required treatment |
|---|---|---|
| 1 | Sidebar | brand (display face + one rotated sticker accent), nav links (contour on active, two-cue active marking: fill + contour), home path (mono, wraps) |
| 2 | Composer (dock) | input (contour, focus ring), send button (primary: live-accent fill, strong contour, resting shadow, press translation) |
| 3 | Overview | status pill, window buttons (active two-cue), live indicator (one rotated "LIVE" sticker), map wrap, map SVG (groups, nodes, edges, labels, arrowheads), text view list, recent-turn rows, section heads |
| 4 | Chat | turn cards (meta row, stage chips, step rows, reply blocks, receipt line), live card |
| 5 | Observability | stat cards (display-face figures), turn track bars, spend table |
| 6 | Memory | stat cards, facts table (forget buttons: bad-accent contour), episodes table, empty states |
| 7 | Settings | form card, labels (micro-label style), inputs, key-set indicator, save button (primary) |
| 8 | Turn-detail overlay | raised panel (resting shadow, strong contour), head, meta, summary, legend, timeline rows, loop disclosures, step `<pre>` blocks, reply, close control |
| 9 | Map text view | `<details>` container, state dots, linkish node buttons |
| 10 | Raw-record panel | `<details>`, mono `<pre>`, wraps anywhere |
| 11 | Live indicator | banner with contour + brand-accent fill + sticker; linkish return action |
| 12 | System states (×3) | empty (`.empty`), loading, error (status pill `data-kind="bad"`, unreachable message) — same contour language, errors never softened |

## Permitted markup hooks (allowlist)

CSS alone is preferred. The only script/HTML changes this feature may make:

| Hook | File | Reason |
|---|---|---|
| `class="card user"` already exists on user messages | render.js | none needed — exists |
| Optional `.brand-sticker` wrapper around the brand word | index.html | rotated sticker behind "byo" cannot be a pseudo-element of a flex child without disturbing layout |
| Optional `.live-sticker` span inside the live indicator | map.js (`overviewView`) | rotated "LIVE" tag |
| Optional `primary` class on send/save buttons | index.html, dock.js | distinguishes the primary action's strong contour + accent fill |

Anything beyond this allowlist is out of scope for the restyle.

## Content parity checklist (must survive unchanged)

Navigation: `Overview`, `Chat`, `Observability`, `Memory`, `Settings`; brand `byo`;
composer placeholder `Ask for something, or say what to remember`; send `Send`.

View heads: `Overview`, `Chat`, `Observability`, `Memory`, `Settings`.

Overview: window buttons `Today / 7 days / All`; status pill default `Agent idle`; live
indicator copy `A new turn is running — return to the map`; `Text view of the map`; section
`Recent turns`; window meta (`today / 7 days / all recorded`); empty `No turns recorded yet.
Say something in the dock to start.`; map labels, summaries and state words (all eight).

Chat: card meta (time, source, turn id), stage chips (`gate · …`, `N loop(s)`, `N tool(s)`,
state), `you ›`, `byo ›`, receipt line (`N call(s) · N tool(s) · … in / … out · USD …`),
empty `Say something below to start.`.

Turn detail: `Turn <id>`, `Close`, legend (`slowest: step N`, `most $: step N`,
`N bad line(s) skipped`), timeline labels (`gate`, `loop N`, `reply`, `memory`,
`error`, `receipt`), hot badges (`slowest`, `most $`), `recorded detail`, raw
(`Raw record (N lines)`), error copy, states `delivered / failed / unfinished`.

Observability: stat labels `turns / tool calls / spend`, `Turns`, `Spend by model`,
table heads `model / USD`, empty `nothing spent yet`, `No turns recorded yet.`,
`no timed steps`.

Memory: stat labels `facts / episodes / mirror`, table heads
`id / subject / fact / source` and `when / what`, `forget`, empties
`nothing remembered yet`, `no episodes yet`.

Settings: labels `provider`, `model`, `API key (a key is set) / (none set)`, placeholder
`paste to replace, never shown again`, `Save`, home line.

Keyboard/behavior parity: hash routing, map node click/Enter/Space, window switching, turn open/
close + focus return, live polling, composer submit (button and Enter), forget and save actions.
No shortcut, route or payload changes.

## Verification

- `test_style_offline.py` + extended `test_map_static.py`: shell still loads the same scripts,
  no external asset appears, allowed hooks only.
- Parity test: the pinned label list above is diffed against the strings in the shell and the
  renderer scripts; any missing label fails.
- Quickstart: every surface row is eyeballed in both schemes; every parity string is ticked on
  one walkthrough.
