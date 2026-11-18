# Data Model — Phase 1

**Feature**: Waku-Parity Minimal Agent Core · **Date**: 2026-11-18

Two persisted shapes, on purpose:

1. **`state.db`** — the system of record for what the agent *knows and did*: calendar events, facts,
   episodes, chat log.
2. **`trajectories/YYYY-MM-DD.jsonl`** — an append-only log of what the agent *did and cost*, one line per
   event. It is the only source for the turn card, the waterfall and the receipt.

Plus three file-shaped stores that exist because a person must be able to read them: the markdown
memory mirror, the outbox, and the persona file (which is configuration, not data).

The trajectory line format is a contract and lives in [contracts/trajectory-schema.md](contracts/trajectory-schema.md).
This document covers the database, the derived read models and the rules that keep the three stores
consistent.

## 1. SQLite schema

The names and columns are the reference's, minus `facts.synced` and `facts.scope` — those two exist
only for the retired hosted-memory integration (FR-002, FR-005). Additions are marked **[additive]**
and change nothing that a reference trajectory or tool relies on.

```sql
-- Calendar artifacts created by the tools.
CREATE TABLE calendar_events (
    id         INTEGER PRIMARY KEY,
    title      TEXT NOT NULL,
    start      TEXT NOT NULL,              -- ISO 8601, local offset included
    "end"      TEXT,
    attendees  TEXT DEFAULT '',            -- comma-separated names
    notes      TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

-- Semantic memory: durable facts.
CREATE TABLE facts (
    id         INTEGER PRIMARY KEY,
    subject    TEXT NOT NULL,              -- who/what the fact is about, e.g. 'alex'
    content    TEXT NOT NULL,
    source     TEXT DEFAULT 'user',        -- 'user' | 'consolidation' | 'tool'
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE VIRTUAL TABLE facts_fts USING fts5(
    subject, content, content=facts, content_rowid=id
);
-- facts_ai / facts_ad / facts_au triggers keep facts_fts in step, exactly as in the reference.

-- Episodic memory: dated things that happened.
CREATE TABLE episodes (
    id          INTEGER PRIMARY KEY,
    happened_at TEXT NOT NULL,             -- ISO 8601 date
    summary     TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE VIRTUAL TABLE episodes_fts USING fts5(
    summary, content=episodes, content_rowid=id
);
-- episodes_ai / episodes_ad triggers.

-- The raw conversation. Consolidation reads the rows where consolidated = 0.
CREATE TABLE chat_log (
    id           INTEGER PRIMARY KEY,
    role         TEXT NOT NULL,            -- 'user' | 'assistant'
    content      TEXT NOT NULL,
    consolidated INTEGER DEFAULT 0,
    session_id   TEXT DEFAULT 'default',
    source       TEXT DEFAULT 'cli',       -- 'cli' | 'dashboard'
    meta         TEXT,                     -- JSON: turn_id, gate decision, iterations, tools
    created_at   TEXT DEFAULT (datetime('now'))
);

-- [additive] Query paths the dashboard reads on every refresh.
CREATE INDEX IF NOT EXISTS chat_log_session ON chat_log (session_id, id);
CREATE INDEX IF NOT EXISTS chat_log_pending ON chat_log (consolidated, id);
CREATE INDEX IF NOT EXISTS facts_subject    ON facts (subject);
```

**Pragmas**: `journal_mode=WAL`, `busy_timeout=3000`, `foreign_keys=ON`. WAL is the one storage
divergence from the reference and exists so the terminal and the dashboard can write at once
(research R7, R14); the `-wal`/`-shm` sidecars are transient and created by SQLite, not by us.

**Migrations**: additive and idempotent, run on every `connect()` — check `PRAGMA table_info`, add
the column if absent, then commit. No version table in v1: the schema is small enough that the
check-then-add pattern (the reference's own approach) stays readable.

## 2. Files under the home directory

| Path | Written by | Read by | Rule |
|---|---|---|---|
| `state.db` | db layer | everything | system of record |
| `trajectories/YYYY-MM-DD.jsonl` | `ops/trajectory.py` | `ops/observability.py`, `ops/show_trajectory.py`, dashboard | one line per event, append-only, never rewritten |
| `MEMORY.md` | `memory/mirror.py` | the person, the dashboard | regenerated from `facts` + `episodes` after every turn and every edit |
| `memory/<id>.md` | `memory/mirror.py` | the person, external importers | one file per fact, front-matter + body, deleted with its fact |
| `outbox/<timestamp>-<slug>.md` | `tools/messages.py` | the person | written once, never modified |
| `PERSONA.md` | `runtime/session.py` on first run, `update_persona`, the person | `runtime/session.py` | the only hand-editable instruction file |
| `.env` | the person, dashboard settings | `config.py` | secrets; never read into a trajectory |

## 3. Derived read models (never persisted)

These are projections over the trajectory, rebuilt on demand so that a trajectory alone can reproduce every
screen (spec US2 AS4).

**Turn** — one `turn_start` … `turn_end` span.

| Field | Derivation |
|---|---|
| `turn_id` | from `turn_start` |
| `user_message`, `source`, `session_id` | from `turn_start` |
| `started_at`, `ended_at` | `ts` of the first and last record |
| `reply`, `iterations` | from `turn_end` |
| `state` | `complete` with a `turn_end`; `unfinished` without one; `failed` when an `error` record precedes the end |
| `steps` | one per `gate`/`llm`/`tool`/`consolidation`/`receipt` record, in file order |

**Step (span)** — one waterfall row: `kind` (`gate`, `llm`, `tool`, `memory_write`, `receipt`),
`label`, `started_at`, `duration_ms` (tool and model calls only), `ok` (`false` for a failed tool or
a `Transport`/`Refused` error), `usd` for `llm` and `receipt`, and a bounded `preview` of arguments
and output.

**Receipt** — `llm` usage summed per turn + `receipt.total_usd`: `{iterations, tool_calls, tokens_in,
tokens_out, usd, estimate}` where `estimate` is true when any call used a model missing from the
pricing table.

**Spend bucket** — group receipts by day and by model for the observability view; never recomputed
from chat text.

**Memory view** — facts and episodes read straight from SQLite, plus counts (`facts`, `episodes`,
unconsolidated rows) and the path of the mirror file.

## 4. Lifecycles

**Turn**

```text
(start) turn_start
   |  gate -> llm -> tool* -> llm -> ...        (any number of loops)
   |  optional: consolidation, receipt
   +--> turn_end                     => complete
   +--> error (provider refused / transport after retry) + turn_end with empty reply  => failed
   +--> process exits / crash                          => unfinished (no turn_end written)
```

Rules: a turn is written even when it fails, so the failure has a card. A turn that crashed never
blocks later turns — the reader groups by `turn_start` and treats a missing `turn_end` as unfinished
(FR-029). `iteration` counts model calls; the tools-off final call after the step limit is recorded
with `kind: "final"` and does not increment the loop count shown on the card.

**Fact**

```text
written by save_note / manage_memory / consolidation  => kept (source recorded)
kept --edit--> updated content + created_at unchanged
kept --forget--> row deleted, FTS row deleted by trigger, memory/<id>.md deleted, MEMORY.md regenerated
```

There is no approval gate in v1: the reference keeps what consolidation proposes, and the person can
correct it. The one suppression rule is at write time — a proposed fact that only repeats text the
turn already recalled is dropped (FR-021, research R11).

**Episode**: appended by consolidation, one per batch, `happened_at` = the local date of the batch's
newest chat row. Episodes are never edited from the UI in v1; deletion follows the fact path.

**Session**: a label on `chat_log` rows, created implicitly by the first message of a thread. The
dashboard's "new chat" changes the label; it never moves rows.

**Outbox message**: `send_message` writes one file and returns its path. No delivery state, no retry,
no network — the tool's honesty rule (FR-018) is that the output names the file.

**Calendar event**: `create_event` inserts one row and returns its id, title, start and the database
path; `list_events` reads a date range ordered by `start`.

## 5. Validation rules

| Rule | Where enforced | Test |
|---|---|---|
| `calendar_events.start` parses as ISO 8601 with an offset | `tools/calendar.py` | `test_calendar.py` |
| A fact has a non-empty `subject` and `content` | `memory/semantic/store.py` | `test_memory.py` |
| `chat_log.role` is `user` or `assistant` | `db.py` check + writers | `test_db.py` |
| `chat_log.consolidated` flips 0 -> 1 once, only for rows that were distilled | `memory/consolidation.py` | `test_consolidation.py` |
| Every trajectory record has `type`, `ts` (ISO 8601 with offset) and, inside a turn, `turn_id` | `ops/trajectory.py` | `test_tracing.py` |
| `turn_start` always carries `trajectory_version: 1` | `ops/trajectory.py` | `test_trajectory_contract.py` |
| Tool arguments and outputs are bounded before they reach a trajectory or a preview | `ops/observability.py` | `test_observability.py` |
| `facts`/`episodes` and the mirror agree row-for-row | `memory/mirror.py` | `test_mirror.py` |
| No credential value reaches a trajectory, a log line or a JSON payload | `ops/trajectory.py` sink | `test_redaction.py` |
| A receipt's `total_usd` equals the sum of its `llm` records (±1e-6) | `ops/receipt.py` | `test_receipt.py` |

## 6. Invariants

- **One trajectory line, one event.** Nothing counts an event twice; nothing drops an event silently.
- **The trajectory is the truth for "what happened".** If the database and the card disagree about a turn,
  the card is right and the database is a convenience.
- **The database is the truth for "what is remembered".** The mirror is a rendering, never a source.
- **Deleting a fact is immediate everywhere**: FTS, mirror file, combined mirror, memory view.
- **No automatic deletion.** Chat rows, facts, episodes and trajectories persist until the person removes
  them (spec Assumptions: retention).
- **Sizes stay bounded where a person sees them**: previews in trajectories, cards and the timeline are
  capped (2000 chars per field by default); the full tool output still reaches the model.

## 7. Scale assumptions

One person, one machine: thousands of chat rows, hundreds of facts, tens of trajectories per day. The
7-day observability window reads at most a few thousand trajectory lines and is expected to stay under
200 ms (plan Technical Context). No pagination in v1; the window selector is the page size.
