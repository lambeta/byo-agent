# Implementation Plan: Weather Query Tool

**Branch**: `008-weather-query-tool` | **Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/008-weather-query-tool/spec.md`

## Summary

Add a seventh agent tool, `query_weather`. It resolves a city name, reads current conditions and
a four-day daily forecast (today plus the next three days) from a public, keyless weather
service, and returns one bounded, source-attributed text block. An ambiguous place comes back as
named candidates instead of a silent guess; every failure becomes a category-tagged text the
model can explain; HTTP work is bounded by a per-request timeout; a small in-memory cache keeps
one fetch per place per turn. The tool is declared through the existing registry, so the terminal
and the dashboard both get it for free — the Tools view already projects the live registry and
the trajectory. No new dependency (stdlib transport), no schema change, no credential.

## Technical Context

**Language/Version**: Python 3.11+ (runtime in this checkout is 3.14.3); stdlib only for the new code.

**Primary Dependencies**: None added. `urllib.request`, `json` and `threading` from the standard
library. The runtime dependency list stays at four (anthropic, openai, python-dotenv, rich).

**Storage**: No schema change and no migration. Weather data is never persisted; a per-process,
time-boxed in-memory cache holds geocoding and forecast responses. The trajectory reuses the
existing `tool_start` / `tool` event types.

**Testing**: Offline deterministic pytest suite (`make eval` / `make gate`). Baseline: 277 tests
passing on 2026-11-19 (30.5 s). New coverage: a fake JSON client with recorded upstream fixtures
for parsing and failures; service tests for resolution, dates, units and caching; tool and
turn-level tests; registry, dashboard, config and env-example updates. No network, no credentials.

**Target Platform**: macOS/Linux local machine; dashboard on 127.0.0.1 loopback.

**Project Type**: local-first agent (CLI + local web dashboard), single repository.

**Performance Goals**: A weather turn completes in ≤ 5 s (p95) when the upstream answers
(SC-002); each upstream request is capped by the configured timeout (default 5 s); a cached place
answers with no network call. A cold place costs two upstream calls (geocode + forecast).

**Constraints**: Offline-first default suite; no new runtime dependency; no credential anywhere
in the tool; three-day horizon; metric default with imperial on request; ambiguity never silently
resolved; secrets redacted at the trace sink; bounded tool output; one upstream failure never
fails a turn.

**Scale/Scope**: One person locally; a handful of cities per turn. One tool, two support modules,
three configuration knobs, one persona rule, tests, and README/.env.example updates. No dashboard
JavaScript change and no database change.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Evidence |
|-----------|---------|----------|
| I. Build From Primitives | PASS | Transport (`urllib.request`), place resolution, caching and rendering are source in this repository. No weather SDK and no framework; stdlib HTTP is a leaf utility. Each new module's docstring states its mechanism and a rejected alternative (research Decisions 1, 2, 9). |
| II. Provider-Agnostic Model Boundary | PASS | No adapter, loop or context-assembly change. The weather upstream is not a model provider; the tool is an ordinary registry entry. The offline suite runs against scripted model adapters and a fake JSON client with no network and no credentials. |
| III. Small Modules With Narrow Contracts | PASS | `byo/weather/client.py` owns JSON-over-HTTP and typed upstream failures; `byo/weather/service.py` owns resolution, dates, cache and shaping; `byo/tools/weather.py` owns the schema and the text contract. Each is testable alone, and the client is injected, mirroring the existing adapter seam. |
| IV. Observable by Default | PASS | Every call flows through the loop's existing `tool_start` / `tool` records (name, args, output, ok, duration), redacted at the sink. Failures are text and marked ok=false; no new writer, no new event type, and the Tools view reads the record unchanged. |
| V. Eval-Driven Behavior Change | PASS | The tool description and one persona rule are prompt-level changes, so the feature ships an eval delta: baseline 277 passing; new cases cover the tool contract, resolution and ambiguity, date bounds, units, error categories, cache dedupe, dashboard payload and a scripted weather turn. The completion report records the post-change count and the cases that moved. |

**Post-design re-check**: PASS. Phase 1 adds no dependency, no schema, no second writer, no
credential and no dashboard code. The cache is in-memory and TTL-bounded; the upstream calls are
keyless and carry no secret. No Complexity Tracking entries are needed.

## Project Structure

### Documentation (this feature)

~~~text
specs/008-weather-query-tool/
├── plan.md              # this file
├── research.md          # Phase 0 — decisions, live probes, rejected alternatives
├── data-model.md        # Phase 1 — entities, validation, error taxonomy, rendering
├── quickstart.md        # Phase 1 — runnable validation scenarios
├── contracts/
│   └── weather-tool.md  # tool schema, text contract, upstream request mapping
└── tasks.md             # Phase 2 output (/speckit-tasks; not created here)
~~~

### Source Code (repository root)

~~~text
byo/
├── config.py                  # + weather_enabled, weather_timeout_seconds, weather_default_place
│                              #   (+ a bool parser and a 1..30 timeout clamp)
├── app.py                     # + optional weather_client seam passed to build_registry
├── tools/
│   ├── __init__.py            # + weather.make_tools; build_registry(..., weather_client=None)
│   └── weather.py             # NEW — query_weather schema, output text, error-to-text mapping
├── weather/
│   ├── __init__.py            # NEW — public seam for the service and its failure types
│   ├── client.py              # NEW — stdlib JSON GET, timeout, status/JSON failure typing
│   └── service.py             # NEW — candidate ranking, place resolution, forecast fetch,
│                              #   date/unit validation, cache, report shaping
├── runtime/session.py         # + one persona rule pointing the model at query_weather
└── ops/static/js/tools.js     # unchanged — registry-driven cards pick the new tool up

evals/
├── fixtures/weather/          # NEW — geocoding and forecast payloads (recorded 2026-11-19)
└── deterministic/
    ├── test_weather_client.py # NEW — status/timeout/JSON failure typing; URL construction
    ├── test_weather_service.py# NEW — resolution, ambiguity, date bounds, units, cache
    ├── test_weather_tool.py   # NEW — text contract, error categories, registry + turn wiring
    ├── test_tools.py          # update the no-memory tool set (now 5)
    ├── test_scope.py          # update the closed tool set (now 7 with memory)
    ├── test_env_example.py    # + the three new knobs
    ├── test_config.py         # + weather defaults and parsing
    └── test_dashboard.py      # + weather card in Available, result row after a turn

.env.example                   # + BYO_WEATHER_ENABLED / _TIMEOUT_SECONDS / _DEFAULT_PLACE
README.md                      # "six tools" -> "seven tools", one line on the weather tool
~~~

**Structure Decision**: Keep the existing single-project layout and seams. Weather splits into
transport, service policy and tool declaration: one file would mix network I/O, resolution
policy, caching and prompt-facing text, which cannot be tested independently. The split keeps
every layer network-free in tests (constitution III) and leaves the dashboard untouched because
the Tools view is already a projection of the registry and the trajectory.

### Implementation sequence (for /speckit-tasks)

1. Config knobs, `.env.example`, and their tests (red, then green).
2. `weather/client.py`: URL construction, timeout, status and JSON failure typing; tests.
3. `weather/service.py`: candidate ranking and resolution, date and unit validation, cache,
   report shaping; fixture-driven tests.
4. `tools/weather.py`: schema, text rendering and error mapping; injection through
   `build_registry` and `Agent`; turn-level scripted tests.
5. Update the closed-set, registry, env-example, config and dashboard tests; README; persona rule.
6. Full suite, lint, eval delta, quickstart.

## Complexity Tracking

No constitution violations; nothing to justify.
