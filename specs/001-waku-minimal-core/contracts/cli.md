# Contract — Command line

**Version**: 1 · **Owner**: `byo/__main__.py`, `byo/gateway/cli.py` · **Tests**: `test_cli.py`

## Commands

| Invocation | Behaviour | Exit |
|---|---|---|
| `byo` | Terminal chat (REPL). Prints a panel with the home path and model, then reads lines. | 0 on `/quit`, `/exit` or EOF |
| `byo dashboard` | Starts the local dashboard on `BYO_PORT` (default 7777), prints the URL, blocks until interrupted. | 0 on Ctrl-C |
| `byo trajectory [file]` | Renders a recorded trajectory as a terminal timeline. Without a file, the newest file in `trajectories/`. | 0 if the file rendered (even with skipped lines), 1 if no trajectory exists |
| `byo --version` | Prints the package version, one line. | 0 |
| `byo --help` / `byo help` | Usage for the three commands. | 0 |
| anything else | Usage on stderr. | 1 |

Chat REPL commands: `/memory` prints a bounded read-only snapshot (facts, recent episodes,
unconsolidated count); `/quit` and `/exit` end the session. Any other line is a user turn.

## Startup rules

- First run creates `BYO_HOME`, `state.db`, `trajectories/`, `outbox/`, `memory/` and `PERSONA.md`.
- Missing provider key: print exactly one line naming the environment variable to set (and the
  `.env` path it would also accept), then **exit 2** — no prompt, no stack trajectory.
- Unknown or unset provider: print the accepted values and exit 2.
- The home directory is printed on startup, because "where is my data" is the first question.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | usage error, unknown command, or no trajectory to render |
| 2 | configuration error: missing key, unknown provider, home not creatable |
| 3 | runtime failure: dashboard port already in use, database unreadable |

## Terminal output rules

- Steps go to stdout as they complete, dimmed and prefixed: `tool · <name>(<args>) → <preview>`,
  `gate · <decision> — <reason>`, `memory · consolidated <n> fact(s)`.
- The reply is printed after the last step, prefixed `byo ›`.
- Errors are printed to stderr; a failed turn still prints a reply line explaining what failed.
- No emoji, no colour when stdout is not a TTY.

## Environment knobs

| Variable | Default | Meaning |
|---|---|---|
| `BYO_HOME` | `~/.byo` | home directory; tests and portable installs override it |
| `BYO_PROVIDER` | `anthropic` | `anthropic` or `openai` (the two wire formats) |
| `BYO_API_KEY` | — | provider credential; required |
| `BYO_BASE_URL` | provider default | override for compatible gateways |
| `BYO_MODEL` | provider default | model id |
| `BYO_SMALL_MODEL` | `BYO_MODEL` | model used by the gate and consolidation |
| `BYO_MAX_ITERATIONS` | `15` | step limit per turn |
| `BYO_MAX_TOKENS` | `8192` | per-call output cap |
| `BYO_HISTORY_TURNS` | `12` | conversation turns kept in working memory |
| `BYO_CONSOLIDATE_EVERY` | `6` | unconsolidated exchanges before consolidation |
| `BYO_RETRIEVAL_TOP_K` | `4` | facts retrieved per turn |
| `BYO_PORT` | `7777` | dashboard port |

Redaction is not a knob: every trajectory record, every streamed frame and every
terminal step line passes through the sink's redaction (spec FR-033).

A `.env` in the home directory is loaded first; the process environment wins over it. No other
file is a source of configuration.

## Parity notes

The verbs, defaults and startup behaviour mirror the reference's; the executable name and the
variable prefix are this project's own (spec FR-001, FR-006). A person who knows the reference types
`byo dashboard` instead of `waku dashboard` and sets `BYO_API_KEY` instead of the reference's key.
