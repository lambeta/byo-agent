---
description: "Task list for the weather query tool"
---

# Tasks: Weather Query Tool

**Input**: Design documents from `specs/008-weather-query-tool/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/weather-tool.md](contracts/weather-tool.md)

**Tests**: Included. The spec requires them (FR-015, SC-006) and the constitution mandates
test-first for loop/tool logic, so every story phase starts with its tests.

**Organization**: Tasks are grouped by user story so each one is an independently testable
increment. Baseline: 277 offline tests passing on 2026-11-19.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependency)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Every task names its exact file path

## Path Conventions

Single project: `byo/` for source, `evals/` for tests and fixtures (see plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Record the upstream payloads every offline test will replay.

- [X] T001 [P] Record geocoding fixtures from Open-Meteo (probed 2026-11-19) into `evals/fixtures/weather/geocode-shanghai.json` (3 candidates: Shanghai Municipality CN population 24874500, two US towns without population), `evals/fixtures/weather/geocode-springfield.json` (≥3 exact-name US candidates, 170188 vs 114394 vs smaller), and `evals/fixtures/weather/geocode-empty.json` (body `{}`, no `results` key)
- [X] T002 [P] Record forecast fixtures into `evals/fixtures/weather/forecast-metric.json` (Shanghai, 4 days, `timezone` "Asia/Shanghai", `current` + `current_units` + `daily` + `daily_units`), `evals/fixtures/weather/forecast-imperial.json` (New York, units °F and "mp/h" and "inch"), `evals/fixtures/weather/forecast-malformed.json` (200 with a missing `daily.temperature_2m_max` entry) and `evals/fixtures/weather/forecast-unit-mismatch.json` (metric request answered in °F)
- [X] T003 [P] Document each fixture's provenance (URL shape, date 2026-11-19, why it exists) in `evals/fixtures/weather/README.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Configuration, transport and shared weather primitives. No user story can render
or fetch without these.

**⚠️ CRITICAL**: Complete before any user story phase.

- [X] T004 Add `weather_enabled` (default `True`), `weather_timeout_seconds` (default 5, clamped 1–30) and `weather_default_place` (default `""`) to `byo/config.py`: new `Settings` fields, a strict boolean parser (true/false, 1/0, yes/no; anything else raises `ConfigError`), and `BYO_WEATHER_*` reading in the one `load_settings` function
- [X] T005 [P] Document the three knobs with their defaults, in the same order as the test's expected set, in `.env.example`
- [X] T006 [P] Add defaults/parsing tests to `evals/deterministic/test_config.py`: enabled true, timeout 5, default place empty, each boolean spelling, invalid boolean raises `ConfigError`, timeout 0 → 1 and 99 → 30
- [X] T007 [P] Extend `evals/deterministic/test_env_example.py`: add the three variables to `EXPECTED` and assert `BYO_WEATHER_TIMEOUT_SECONDS` equals the code default
- [X] T008 Create `byo/weather/client.py`: `JsonClient` protocol with `get_json(url) -> dict`; `HttpJsonClient(timeout)` using `urllib.request` with a `User-Agent` naming this build, the configured timeout, a 200 KB body cap, UTF-8 decode; raise `ServiceUnavailable` for URL errors, timeouts, HTTP 429 and 5xx, and `BadData` for non-JSON or a non-object root; carry a design note with one rejected alternative
- [X] T009 [P] Create `evals/deterministic/test_weather_client.py` covering 429, 500, timeout, DNS/URL error, non-JSON body, JSON root that is not an object, the 200 KB cap and the `User-Agent` header, plus URL construction for the two endpoints
- [X] T010 Create `byo/weather/service.py` scaffolding: `Place`, `CurrentReading`, `DailyForecast`, `WeatherReport`, `WeatherFailure` value types from [data-model.md](data-model.md); the WMO code → phrase table ("WMO code N" for unknown codes); unit maps metric °C/km/h/mm and imperial °F/mph/inch that normalise the provider spelling "mp/h" to mph; a lock-guarded TTL cache with geocode TTL 3600 s, forecast TTL 60 s, 128-entry cap with oldest-first eviction, and no caching of failures
- [X] T011 [P] Create `evals/deterministic/test_weather_service.py` scaffolding tests: known and unknown WMO codes, unit normalisation including "mp/h", cache hit within TTL, miss after TTL (injected clock), 128-entry eviction, and failures never cached

**Checkpoint**: `test_weather_client.py`, `test_weather_service.py`, `test_config.py` and `test_env_example.py` pass offline; no network touched.

---

## Phase 3: User Story 1 - Current weather for a named place (Priority: P1) 🎯 MVP

**Goal**: A person asks for the weather in a city and gets current conditions, the resolved
place, the local reading time and units — with one fetch per place per turn.

**Independent Test**: Offline, drive one scripted-model turn asking for current weather in
Shanghai through `Agent(..., weather_client=FakeClient(forecast-metric.json, geocode-shanghai.json))`;
verify one `query_weather` call with the resolved place, the fixture's temperature/condition in
the reply, the tool event recorded `ok: true`, and the `/api/tools` payload carrying the card.

### Tests for User Story 1 ⚠️ (write first; they must fail)

- [X] T012 [P] [US1] Add resolution tests to `evals/deterministic/test_weather_service.py`: exact-name filtering, single candidate accepted, population dominance ≥ 5× resolves ("Shanghai": 24874500 vs 0; "上海" via a `language=zh` query), a non-dominant set returns `WeatherFailure(category="place ambiguous")` without candidates yet, a comma hint ("Springfield, Illinois") filters by admin1/country, missing population counts as 0
- [X] T013 [P] [US1] Add tool, render and wiring tests to `evals/deterministic/test_weather_tool.py`: schema requires `place` and offers `units` enum metric|imperial; the rendered block has the header (resolved "Name, admin1, country", timezone, "read … local"), a "Now" line with °C, %, km/h, mm and the attribution line; registry has 5 tools without memory and 7 with it; a scripted turn records `query_weather` `ok: true`; `/api/tools` includes the card; `BYO_WEATHER_ENABLED=false` removes it from registry and payload

### Implementation for User Story 1

- [X] T014 [US1] Implement geocoding and place resolution in `byo/weather/service.py`: call the geocoding URL with `count=8`, `language=zh` when the query contains CJK else `en`, `format=json`; apply the comma-hint filter, exact-name filter, population ranking (missing = 0) and the ≥ 5× dominance rule from [research.md](research.md) Decision 3
- [X] T015 [US1] Implement the forecast fetch and current shaping in `byo/weather/service.py`: build the forecast URL with the current/daily field lists, `timezone=auto`, `forecast_days=4` and the metric/imperial parameters; validate `current_units`/°C vs °F, km/h vs mp/h/mph, mm vs inch; a missing, non-numeric or mislabelled value becomes `WeatherFailure(category="data unavailable")`
- [X] T016 [US1] Create `byo/tools/weather.py`: `query_weather` `Tool` (description, schema: `place` required, `units` enum, no `start`/`end` yet), the header + "Now" + attribution renderer, and the failure-to-text mapping that prefixes `Error: ` with one of the five categories; return text and never raise for expected failures
- [X] T017 [US1] Add `byo/weather/__init__.py` exports, `weather.make_tools(conn, settings, client=None)` registration in `byo/tools/__init__.py` behind `settings.weather_enabled`, and the `weather_client=None` seam through `build_registry` and `Agent` in `byo/app.py`; update the closed-set docstring
- [X] T018 [US1] Update the closed sets: `evals/deterministic/test_tools.py` no-memory expectation to 5 and `evals/deterministic/test_scope.py` to the 7-tool closed set (tool list in [data-model.md](data-model.md) "Configuration and tool-set changes")
- [X] T019 [US1] Add the persona rule to `DEFAULT_PERSONA` in `byo/runtime/session.py`: use `query_weather` for current conditions or the next three days in a named place, and state the place and local reading time

**Checkpoint**: US1 works offline end to end; 5/7-tool tests and dashboard card test green.

---

## Phase 4: User Story 2 - Another day or a short range (Priority: P2)

**Goal**: The same place answer works for tomorrow and a short range, one line per day, and
never fabricates a day outside the three-day horizon.

**Independent Test**: Offline, run a turn asking about tomorrow with the metric fixture; verify
the tool received the explicit ISO date and one daily line is rendered; then ask for a day beyond
today + 3 and verify the reply states the window and presents no forecast.

### Tests for User Story 2 ⚠️ (write first; they must fail)

- [X] T020 [P] [US2] Add range tests to `evals/deterministic/test_weather_service.py`: no dates → today..today+3 (place-local), `start` only → single day, `start`+`end` ascending, unparseable date, `start > end`, date before today and date after today+3 each become `WeatherFailure(category="request out of range")` carrying the explicit window, daily arrays must share one length ≥ 1 and start on `start`
- [X] T021 [P] [US2] Add daily render and turn tests to `evals/deterministic/test_weather_tool.py`: schema offers optional ISO `start`/`end`; one daily line per requested day in ascending order with ISO dates, high–low range, rain chance and amount with units; the out-of-range text names the window (today..today+3); a scripted "tomorrow" turn passes the explicit date

### Implementation for User Story 2

- [X] T022 [US2] Add the `start`/`end` parsing and place-local window validation to `byo/weather/service.py`: defaults, ordering, the [today, today+3] window from the forecast timezone, and the `request out of range` failure with explicit dates
- [X] T023 [US2] Add daily shaping to `byo/weather/service.py`: consume the five `daily` arrays, validate shared length and start-date alignment, slice to the requested range, attach condition/high/low/chance/amount
- [X] T024 [US2] Extend `byo/tools/weather.py`: add `start`/`end` to the schema and render the "Daily:" block (one line per day, dates echoed), keeping the attribution line last

**Checkpoint**: US1 and US2 both test independently; the range boundary is proven by fixtures, not live data.

---

## Phase 5: User Story 3 - Honest failures and visible calls (Priority: P3)

**Goal**: Unknown or ambiguous places, empty places, timeouts, rate limits, malformed payloads and
unit mismatches all produce plain, categorised text; every call is visible in the trajectory and
the dashboard Tools view.

**Independent Test**: Offline scenarios for each failure use counting fake clients; verify each
turn completes, the model receives the categorised text, the trajectory records `ok: false`, and
`/api/tools` shows the weather card plus the failed result row.

### Tests for User Story 3 ⚠️ (write first; they must fail)

- [X] T025 [P] [US3] Add failure tests to `evals/deterministic/test_weather_tool.py`: unknown place → `place not recognised`; ambiguous → up to five "Name, admin1, country" candidates; empty place with `BYO_WEATHER_DEFAULT_PLACE` set resolves the default, without it refuses; timeout/429/5xx → `service unavailable` with a retry hint; non-JSON/misaligned arrays/unit mismatch → `data unavailable`; every failure text starts with `Error: ` and the turn still returns a reply
- [X] T026 [P] [US3] Add visibility tests to `evals/deterministic/test_dashboard.py` and `evals/deterministic/test_weather_tool.py`: a scripted weather turn makes `/api/tools` contain the `query_weather` card and a Results row with tool, ok/error, duration and output preview; a failing call records `ok: false` in the trajectory; the recorded output contains no credential and ends with the attribution line
- [X] T027 [US3] Add a cache-dedupe test to `evals/deterministic/test_weather_service.py`: a counting fake client proves two same-place calls in one turn make exactly one geocode and one forecast request (TTL 3600 / 60, per [data-model.md](data-model.md))

### Implementation for User Story 3

- [X] T028 [P] [US3] Implement the full failure taxonomy in `byo/tools/weather.py`: five categories with their guaranteed content from [contracts/weather-tool.md](contracts/weather-tool.md) §3 — candidate list formatting, retry hint for `service unavailable`, window text for `request out of range`, and the "ask for a clearer place" wording for `place not recognised`
- [X] T029 [US3] Implement candidate ranking/formatting ("Name, admin1, country", up to five, population-ordered) in `byo/weather/service.py` and the `BYO_WEATHER_DEFAULT_PLACE` fallback for an empty place; keep the dominant-candidate rule unchanged
- [X] T030 [US3] Verify and fix candidate/turn ordering in `byo/tools/weather.py` and `byo/weather/service.py`: the ambiguity reply never includes a temperature, the failed call leaves the trajectory records in order (`tool_start` then `tool`), and a second call after a cached failure is not served from cache

**Checkpoint**: All three stories are independently functional; failure paths are pinned offline.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, lint, eval delta and the quickstart, all after the stories land.

- [X] T031 [P] Update `README.md`: "six tools" → "seven tools" in the Tools-view paragraph, plus one sentence describing `query_weather` and the keyless data source
- [X] T032 [P] Confirm every new module (`byo/weather/client.py`, `byo/weather/service.py`, `byo/tools/weather.py`) opens with a mechanism note and at least one rejected alternative, matching the existing module style
- [X] T033 Run `make lint` and fix any ruff findings in `byo/weather/`, `byo/tools/weather.py`, `byo/config.py`, `byo/app.py`, `byo/runtime/session.py` and `evals/deterministic/test_weather_*.py` (line length 100, the repo's selected rules)
- [X] T034 Run the full offline suite (`make eval`, i.e. `evals/deterministic`); record the eval delta against the 277-test baseline, listing the new cases and confirming no previously passing test regressed
- [X] T035 Validate [quickstart.md](quickstart.md) sections 1, 2, 4, 6, 7 and 8 (offline and dashboard Checks with a dummy key); leave sections 3 and 5 (live model/network) as documented optional checks
- [X] T036 Final consistency pass: re-read [contracts/weather-tool.md](contracts/weather-tool.md) and [data-model.md](data-model.md) against the code — TTLs 3600/60, 128 entries, 200 KB cap, 8 candidates, 5× dominance, 5 candidate cap, three env knobs, output line order — and fix whichever side drifted

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies; T001–T003 are parallel.
- **Foundational (Phase 2)**: depends on Setup (fixtures feed the tests). T004–T007 touch config/docs/tests; T008–T011 build the client and service scaffolding.
- **US1 (Phase 3)**: depends on Foundational. No dependency on US2/US3.
- **US2 (Phase 4)**: depends on US1 (it reuses the location and forecast fetch US1 builds). It adds dates and daily shaping only.
- **US3 (Phase 5)**: depends on US1 and US2 (its failures include the range failure US2 introduces).
- **Polish (Phase 6)**: depends on all three stories.

### User Story Dependencies

- **US1 (P1)**: independent after Foundational — the MVP.
- **US2 (P2)**: needs US1's place resolution and forecast fetch; daily rows are additive.
- **US3 (P3)**: needs US1/US2 outcomes to have something to harden; its tests are independent of each other.

### Within Each User Story

- Tests before implementation; they must fail first.
- Service logic before tool rendering; tool before wiring.
- Registry/closed-set updates in the same change as the wiring (T017–T018 together).
- Story complete before moving to the next priority.

### Parallel Opportunities

- T001/T002/T003 (fixture recording and its README) run in parallel.
- T005/T006/T007 (env docs and config tests) run in parallel with T008/T009 (client and its tests).
- T012/T013 (US1 tests in two different files) run in parallel; T015/T016 touch different files.
- T020/T021 (US2 tests) and T025/T026 (US3 tests) run in parallel within their phases.
- T031/T032 (README and design notes) run in parallel in Polish.

---

## Parallel Example: User Story 1

~~~bash
# Write the two failing test files together:
Task: "Add resolution tests in evals/deterministic/test_weather_service.py"
Task: "Add tool/render/wiring tests in evals/deterministic/test_weather_tool.py"

# Then implement the tool and the service in parallel (different files):
Task: "Implement geocoding/resolution in byo/weather/service.py"
Task: "Create query_weather in byo/tools/weather.py"
~~~

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: record fixtures.
2. Phase 2: config, client and service primitives.
3. Phase 3: US1 — a person can ask for the current weather in a city, offline-proven.
4. **STOP and VALIDATE**: run the US1 independent test; open the dashboard Tools view.
5. Demo if ready; US1 alone already ships the seventh tool.

### Incremental Delivery

1. Foundation → US1 → validate → ship (MVP).
2. Add US2 → validate tomorrow/range and the out-of-range boundary → ship.
3. Add US3 → validate every failure category and the trajectory/dashboard visibility → ship.
4. Polish: README, lint, eval delta, quickstart.

### Notes

- Tests must fail before implementation; the fake JSON client is the only network seam and never
  touches the network.
- No dependency may be added; the transport is stdlib.
- Keep `.env.example`, `test_env_example.py` and `Settings` in one edit each (T004–T007) so the
  documented-knob test cannot drift.
- Record the eval delta in the implementation report: baseline 277, post-change count, new cases.