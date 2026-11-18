# Validation Note: Neobrutalist Dashboard Refresh

**Date**: 2026-11-19 | **Feature**: [spec.md](spec.md) | **Tasks**: [tasks.md](tasks.md)

## Automated evidence (this session)

| Criterion | Evidence | Result |
|---|---|---|
| SC-002 content parity | `test_style_parity.py` — 60+ pinned labels from contracts/surface-parity.md diffed against shell + scripts | PASS |
| SC-003 contrast (computed) | `test_style_tokens.py` — 11 pairs × 2 schemes via WCAG relative luminance; min observed 4.64:1 (ink-on-accent on live, light) | PASS |
| SC-004 reflow (static part) | 900px and 420px breakpoints in style.css; map keeps the only horizontal scroll region | PASS (browser pass pending) |
| SC-006 grayscale cues | `test_style_states.py` — 8 `data-state` selectors, running/failed strong contour, 4 dashed states | PASS (naming pass pending) |
| SC-010 offline | `test_style_offline.py` — zero `@import`, `http(s)://`, `cdn.`, remote `url()` in every static asset | PASS |
| FR-004 type floor | `test_style_tokens.py` — 14px / 12.5px / 11px floor pinned | PASS |
| FR-014 self-contained | no new dependency, no font request, no build step; `pyproject.toml` untouched | PASS |
| FR-015 parity of behavior | `test_map_static.py` extended (7-script order, static serving); full suite 155 tests green | PASS |
| Suite | `pytest evals/deterministic` 155 passed; `ruff check` clean | PASS |
| Live smoke | dashboard on 127.0.0.1:7777 serves the new stylesheet; `/api/health`, `/api/data`, `/api/map` OK | PASS |

## Pending manual (browser) verification

Headless screenshots were blocked by the file sandbox (Chrome needs ~/Library writes;
escalation was not approved), so these quickstart.md scenarios remain for a human pass:

- Scenario 2–3: five-view walk in both schemes (visual identity, hierarchy)
- Scenario 4: live turn lighting on flat fills (or scripted substitute)
- Scenario 5: keyboard-only path, focus return
- Scenario 6: 1280/900/375 + 200% zoom reflow
- Scenario 7: grayscale 8/8 state naming
- Scenario 8: edge-case sweep (fresh home, feed drop, forced colours, long content)
- Scenario 9: label-by-label parity walkthrough

Run: `uv run byo dashboard` → http://127.0.0.1:7777 and follow quickstart.md.
## Addendum 2026-11-19: dual scheme, light default

At the user's direction the scheme mechanism changed: light is now the default `:root`
token set, dark is a `:root[data-theme="dark"]` override chosen by a sidebar theme switch
(persisted in localStorage, no OS dependency). Tests updated accordingly; suite re-run green.
Manual re-check of quickstart scenarios 3 (both schemes) now uses the switch instead of the OS.
## Addendum 2026-11-19: bento grid + right chat rail

Layout change at the user's direction: the bottom dock is gone; chat is a persistent right rail
(360 px, history + live card + composer) and the main view is a 6-column bento grid with
`.bento-4`/`.bento-2` spans (Observability, Memory, Settings, Overview recent/text cells).
The `#chat` nav entry now focuses the composer instead of switching views. Copy touchpoints
updated ("Say something in the composer to start."). Suite 157 green, ruff clean; served markup
verified on a scratch port (7799) because 7777 was occupied by another app at test time.
## Addendum 2026-11-19: shell rebuilt on the waku layout structure

At the user's direction the bento experiment was reverted and the shell rebuilt on the
reference project's layout anatomy (structure only — no assets, copy or code copied):
left rail with grouped sections + collapse-to-letters, main with a page head
(title + subtitle + actions), right chat dock with a drag resizer, collapse button and a
fixed "‹ Chat" reopen handle, composer is an autogrowing textarea (Enter sends, Shift+Enter
newlines). Dock width persists in localStorage. The Neobrutalist token skin is unchanged.
Suite 157 green, ruff clean; shell markers verified on scratch port 7799.
## Addendum 2026-11-19: chat interaction and session history fixes

Reported problem: "Chat 的交互和历史会话有些问题". Diagnosed defects and fixes:

1. **History was a turn-card dump, not a conversation.** The dock rendered observability
   turn cards (all sources, CLI included). Now the dock renders chat_log as user/assistant
   bubbles for the active session via `GET /api/session?action=history`; the detailed live
   card remains only while a turn streams.
2. **Sessions existed in the schema but not in the UI.** Added `POST /api/session
   {action:"new"}` (`Agent.new_session()` → `s-YYYYMMDD-HHMMSS`, resets working history,
   past sessions stay in chat_log), a real `current` in `GET /api/session`, a "+ New chat"
   button and a history picker; past sessions are read-only and sending returns to the
   current chat.
3. **Enter submitted mid-IME-composition** (CJK input). Guarded with
   `event.isComposing || keyCode === 229`.
4. **No scroll management.** The log follows new messages (scrollChat on send/stream/refresh);
   a generation counter discards stale history loads.

Tests: `test_dashboard.py` gains session split/history/400 coverage; parity pins gain the
new controls. Scoped run: 26 passed. Note: a concurrent session (specs/004) was mid-edit on
app.py/dashboard.py during this change; the repo-wide suite has 2 failures in THEIR scope
(test_map.py, test_map_api.py), so this change is deliberately left uncommitted until their
session settles.
