# Phase 0 Research: Weather Query Tool

**Date**: 2026-11-19 | **Feature**: specs/008-weather-query-tool

This feature adds a seventh tool, `query_weather`, that answers current weather and a short daily
forecast for a named city. The spec fixed the two scope decisions up front: coverage is today plus
the next three days (clarification B), and the data source is a live public service that needs no
API key (clarification A). The decisions below turn that into a concrete design, record the live
probes that shaped it, and name the alternatives that were rejected.

Baseline before implementation: the offline deterministic suite passes, **277 tests** collected and
green on 2026-11-19. No live-model call is involved in this feature.

Both upstream endpoints were probed from this checkout on 2026-11-19; the shapes quoted below are
recorded responses, not documentation guesses. The fixtures the tests will use come from the same
probes.

## Decision 1: Upstream is Open-Meteo (geocoding + forecast), keyless

**Decision**: Use two public HTTPS endpoints from Open-Meteo:

- Geocoding: `GET https://geocoding-api.open-meteo.com/v1/search?name=<place>&count=8&language=<en|zh>&format=json`
- Forecast: `GET https://api.open-meteo.com/v1/forecast?latitude=<lat>&longitude=<lon>&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m,precipitation&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum&timezone=auto&forecast_days=4`

Neither needs a key, a header credential or an account. The tool output carries the provider's
required attribution ("Weather data by Open-Meteo.com"); the service is free for non-commercial use
and rate-limits callers, which the tool treats as a "service unavailable" failure with a retry hint.

**Rationale**: This is the only mainstream option that satisfies clarification A end to end —
geocoding and forecast from one provider, JSON, WMO weather codes, local time zones, unit
parameters, and a 4-day daily forecast. It also keeps the dependency budget intact (plain HTTPS
JSON, no SDK). The probed response for Shanghai at 2026-11-19 showed everything the contract
needs: `current_units` / `current` with temperature, apparent temperature, humidity, code, wind
speed/direction and precipitation; `daily` arrays aligned by date; `timezone`: "Asia/Shanghai";
`utc_offset_seconds`; and `forecast_days=4` returning today plus three days.

**Alternatives considered**:
- OpenWeatherMap: rejected. Needs an API key (clarification A excludes credentials), and the
  free tier's forecast shape and unit handling would add mapping work for no gain here.
- wttr.in: rejected. Human-oriented text/HTML output; parsing it would make the contract a
  scraping exercise and would fail silently when the format drifts.
- weather.gov: rejected. US-only coverage, contrary to the spec's named-place journeys.
- A bundled/offline dataset: rejected by clarification A — the product must answer with real
  weather. Offline data remains only as test fixtures.

**Risk recorded**: the provider's rate limits and terms can change. The tool exposes a clear
"service unavailable (rate limited)" category rather than hiding it, and the endpoint constants
live in one module so a future change is one edit.

## Decision 2: Standard-library transport; no new dependency

**Decision**: Implement the JSON GET in `byo/weather/client.py` with `urllib.request`. Build a
`Request` with a `User-Agent` naming this build, apply the configured timeout, cap the body read
at 200 KB, decode UTF-8, and `json.loads`. Map failures to three typed upstream errors:
`ServiceUnavailable` (URL error, timeout, HTTP 429, HTTP 5xx), `BadData` (non-JSON body, wrong
root type) and, at the service layer, missing/ill-typed fields become `BadData` too.

**Rationale**: The constitution's dependency budget is four and is asserted by tests
(`test_dependency_budget_is_four_and_framework_free`, `test_runtime_dependency_budget`). HTTP is a
leaf utility; the standard library covers it. Typed errors at the transport boundary let the
service map one failure point to the spec's categories without inspecting exception strings.

**Alternatives considered**:
- `requests` or `httpx`: rejected. A new runtime dependency for a single GET pattern, and the
  budget test treats it as a budget change requiring justification in plan.md.
- A provider SDK: rejected. It would own HTTP and parsing (an opaque dependency), add a code
  surface, and still need the same error mapping.
- Shelling out to `curl`: rejected. A child process adds a platform dependency and text parsing.

## Decision 3: Place resolution ranks candidates and refuses to guess

**Decision**: Search up to 8 candidates. If the query contains a comma ("Springfield, Illinois"),
use the first segment as the name and match the remaining tokens against each candidate's
`admin1`, `admin2`, `country` and `country_code`. If any candidate's name equals the query
(case-folded), keep only those. Rank by population (missing = 0), then resolve when exactly one
candidate remains **or** the top candidate's population is at least 5× the runner-up. Otherwise
return `place ambiguous` with up to five candidates formatted "Name, admin1, country". No
candidates at all is `place not recognised`.

**Rationale**: Population dominance is what makes common names usable without guessing: the live
probe for "Shanghai" returned three exact-name matches (Shanghai Municipality, CN, population
24.8 M; two US towns with no population), and "上海" returned the same pattern (24.8 M vs two
small villages). A strict exact-name rule would wrongly call Shanghai ambiguous; a
first-result rule would silently pick Alabama for a mild typo. Springfield is the control case:
170 k vs 114 k vs more — no dominance, so the tool asks which Springfield, exactly as FR-003
requires. The rule is deterministic, documented, and pinned by tests with recorded fixtures.

**Alternatives considered**:
- Always take the first result: rejected. That is the silent choice FR-003 forbids.
- Strict exact-name match only: rejected. It breaks the most common queries (Shanghai, 上海) as
  shown by the probe.
- Ask the person inside the tool: rejected. A tool call returns text once; ambiguity is reported
  to the model, which can ask in the conversation.
- Require coordinates: rejected. The spec's journeys are city names, and it would push geocoding
  into the model.

**Data note**: the geocoding response omits `population` for small places and includes
`feature_code`; both are handled. The tool prints the resolved "Name, admin1, country" so the
person can catch a wrong pick, and the reply's date/time zone comes from the forecast response.

## Decision 4: Dates are ISO in the schema; relative phrases stay the model's job

**Decision**: The tool schema takes optional `start` and `end` as ISO dates (YYYY-MM-DD). Defaults:
no start means today in the resolved place's time zone; no end means the same day as start. The
allowed window is today through today + 3 days (place-local). Validation errors (unparseable date,
start after end, date in the past, date beyond the horizon) return `request out of range` with the
supported window in the message. The output always echoes the explicit dates it used, and the
persona rule tells the model to resolve "today/tomorrow/this weekend" against the clock the session
already injects into the system prompt.

**Rationale**: `session.build_system` already gives the model the current local date and time, and
natural-language date parsing is model competence, not tool competence. Keeping the tool's input
strictly ISO makes the contract testable and stops a second, locale-dependent parser from drifting
against the model's calendar. `timezone=auto` makes the provider align daily arrays to the place's
local dates, and the probe confirmed `timezone` (Asia/Shanghai) plus a local `current.time`.

**Alternatives considered**:
- Parse "tomorrow"/"weekend" inside the tool: rejected. Duplicates the model's job, drags locale
  and phrase coverage into the tool, and is harder to test.
- Compute dates in UTC: rejected. "Tomorrow" would be wrong for places near the date line.
- Take a `days` integer only: rejected by the spec's range request; ISO dates are clearer.

## Decision 5: Units map to provider parameters and to rendered labels

**Decision**: `units` is an optional enum, `metric` (default) or `imperial`. Metric sends
`temperature_unit=celsius`, `wind_speed_unit=kmh`, `precipitation_unit=mm` and renders °C, km/h,
mm. Imperial sends `fahrenheit`, `mph`, `inch` and renders °F, mph, inch. Wind direction degrees
become a 16-point compass label ("NW"), and every number in the output carries its unit.

**Rationale**: FR-010 requires both systems and labelled units. The probe confirmed the provider
honours all three unit parameters (°F, "mp/h" and "inch" in the response; note the provider spells
mph as "mp/h", so unit metadata is normalised before validation while the rendered label stays
"mph"); no client-side conversion code is needed, so there is nothing to drift. The cache key
includes units because the provider payload differs.

**Alternatives considered**:
- Convert client-side from metric: rejected. More code, rounding drift, and the provider already
  returns units metadata.
- Only metric: rejected by FR-010.

## Decision 6: Failures become category-tagged text, never exceptions

**Decision**: Every failure is returned as a string starting with `Error: `:
`place not recognised`, `place ambiguous` (with candidates), `data unavailable`, `service
unavailable` (with a retry hint, covering timeout, 429 and 5xx), `request out of range` (with the
window). The tool catches its own typed errors and formats this text; it never raises for expected
failures. Unexpected bugs still fall through to the registry's existing conversion, which is the
project's last-resort behaviour.

**Rationale**: The registry marks `ok = not output.startswith("Error:")`, and the loop feeds the
text back to the model — that is exactly the trajectory and dashboard contract US3 asks for. If
the tool raised, the registry would render "Error: ServiceUnavailable: ..." and the category would
be buried in an exception class name. Ambiguity carries the candidate list so the model can ask a
useful follow-up instead of apologising.

**Alternatives considered**:
- Raise typed exceptions: rejected. Loses the category in the registry's formatting and blurs
  expected refusals with bugs.
- Return a structured dict: rejected. The loop passes strings to the model; a dict would become
  its repr.
- Fall back to a default city: rejected. A silent wrong answer is the defect the spec names.

## Decision 7: A small in-process TTL cache keeps one fetch per place per turn

**Decision**: Keep two dictionaries in the service instance, guarded by a `threading.Lock`:
geocoding keyed by (normalized query, language) with a 1-hour TTL, forecasts keyed by
(latitude rounded to 4 decimals, longitude rounded to 4, units) with a 60-second TTL. Cap the
dictionary size (128 entries, evict oldest). Exact-error results are not cached.

**Rationale**: FR-014 asks for no duplicate call within a turn; TTLs also protect a rate-limited
public service when the person asks about the same city twice in a row. No persistence means no
stale "current weather" claim survives a restart, and no new storage appears. The dashboard runs
one turn at a time behind its lock, but the CLI thread and request threads can read; the small lock
keeps that safe.

**Alternatives considered**:
- No cache: rejected. A follow-up question in one turn would re-hit the provider, exactly the
  duplicate FR-014 forbids.
- Persist to SQLite: rejected. Weather is ephemeral; a table would add schema and staleness rules
  for no product value.
- Rely on the provider's own caching: rejected. It does not dedupe this process's requests and
  cannot be observed in tests.

## Decision 8: Three configuration knobs, one reader

**Decision**: Add `byo.config.Settings.weather_enabled` (default `True`),
`weather_timeout_seconds` (default 5, clamped to 1–30) and `weather_default_place` (default
empty), read from `BYO_WEATHER_ENABLED`, `BYO_WEATHER_TIMEOUT_SECONDS` and
`BYO_WEATHER_DEFAULT_PLACE`. Add a strict boolean parser (true/false, 1/0, yes/no; anything else
raises `ConfigError`). Update `.env.example` and the env-example test's expected set. When
disabled, `build_registry` simply does not add the tool, so the dashboard's Available list and the
model's schema list both reflect the setting. When the person asks about "here" with no place and
a default is configured, the default is used; otherwise the tool returns a readable
"place not recognised" asking for a city.

**Rationale**: FR-012 and the constitution's "configuration over hardcoding" require the tool to
be switchable, and the existing pattern is one Settings object with one reader. `test_env_example`
asserts the documented knobs match the code exactly, so the three additions are pinned in the
same change. The default-place knob turns the "这里天气" edge case into a configured answer without
guessing from an IP address.

**Alternatives considered**:
- A generic `BYO_TOOLS` allowlist: rejected for this slice. It changes how every tool is enabled
  and touches tests for all of them; a dedicated flag is smaller and matches FR-012.
- Hardcode enabled/5 s: rejected by the configuration rule.
- Let the model pass a timeout: rejected. A safety budget is not a request parameter.

## Decision 9: Three seams, and the client is injected

**Decision**: `byo/weather/client.py` defines the `JsonClient` protocol (`get_json(url) -> dict`)
and `HttpJsonClient(timeout)`. `byo/weather/service.py` defines `WeatherService(client, clock=None)`
owning resolution, validation, cache and report shaping. `byo/tools/weather.py` defines
`make_tools(conn, settings, client=None)`. `build_registry(conn, settings, memory=None,
weather_client=None)` and `Agent(..., weather_client=None)` pass the seam through. Tests inject a
fake client; production constructs `HttpJsonClient(settings.weather_timeout_seconds)`.

**Rationale**: This mirrors the project's only other external seam — the model adapter, which is
an injected object with a scripted test double. Each layer is testable in isolation: the client
against a stub opener, the service against a fake client, the tool against a fake service result.
The dashboard and CLI need no knowledge of weather.

**Alternatives considered**:
- Monkeypatching `urllib.request.urlopen`: rejected. Global, order-sensitive and invisible in the
  call graph.
- One module for client + service + tool: rejected. It mixes network I/O, policy and prompt-facing
  text, and cannot be tested without patching.
- Passing a client through `Settings`: rejected. Configuration must not carry live objects.

## Decision 10: WMO codes become phrases; attribution is part of the output

**Decision**: Translate the provider's WMO weather codes to short English phrases (clear sky,
mainly clear, partly cloudy, overcast, fog, drizzle, rain, freezing rain, snow, showers,
thunderstorm, and the hail variants), with "WMO code N" for an unknown code. End the tool output
with "Weather data by Open-Meteo.com" and the local read time.

**Rationale**: The model should receive readable conditions, not integer codes it must look up;
the mapping is one table, tested at known and unknown codes. The provider's terms require
attribution, and putting it in the tool output makes it visible to the person without a second
source.

**Alternatives considered**:
- Pass raw codes: rejected. Invites model misreading and inconsistent phrasing.
- Ask the model to translate: rejected. It has no code table in context and would guess.
- Omit attribution: rejected. It breaches the provider's licence.

## Decision 11: One persona rule, measured by the eval delta

**Decision**: Add one rule to `session.DEFAULT_PERSONA`: use `query_weather` for current
conditions or the next three days in a named place, and state the place and local reading time.
Keep the tool description as the detailed contract. Treat both as prompt changes under
constitution V.

**Rationale**: The existing persona lists one rule per tool and is created on a person's first
turn; without a weather rule the model under-calls the tool, and a second system-prompt source for
tool guidance would be redundant. The eval delta records the scripted turn that exercises the rule.

**Alternatives considered**:
- Tool description only: rejected. Weaker guidance and no place/time honesty rule.
- A per-turn injected weather section: rejected. A second source of truth for the same contract.

## Decision 12: Offline doubles plus recorded fixtures; explicit eval delta

**Decision**: Record the probe payloads as fixtures under `evals/fixtures/weather/` (a resolved
place, an ambiguous place, an empty result, a 4-day forecast, a malformed payload, and an imperial
forecast). Add `test_weather_client.py`, `test_weather_service.py` and `test_weather_tool.py`;
update `test_tools.py` (no-memory tool set becomes 5), `test_scope.py` (closed set becomes 7),
`test_env_example.py` (three knobs), `test_config.py` (defaults/parsing) and `test_dashboard.py`
(weather card in Available, weather result after a turn). No live HTTP in the default suite.

**Rationale**: Constitution II and V require an offline, credential-free suite. The fake client
plus recorded payloads exercise the real service, tool and loop; the existing scripted adapter
drives the model side. The dependency budget test stays untouched because nothing was added.

**Alternatives considered**:
- Live provider calls in the suite: rejected. Network and rate limits would make the suite flaky.
- A VCR/cassette dependency: rejected. A new dependency to replay JSON we can store as plain files.
- Monkeypatch-only tests: rejected. They would not pin the client's own mapping.

**Eval delta**: baseline 277 tests pass in 30.5 s. The feature adds the three weather test modules
and the updated contract tests; the completion report records the post-change count, the added
cases and the scripted turn, with no network and no credentials.

## Decision 13: Documentation duty carried into the code

**Decision**: Each new module opens with a short design note (mechanism plus at least one rejected
alternative), matching the existing modules. Update the README's tool count ("six" → "seven") and
add one sentence describing the weather tool; document the three knobs in `.env.example`.

**Rationale**: Constitution I and the Documentation duty require the "why" next to the "how"; the
README is the person-facing map and currently says six tools.

**Alternatives considered**:
- README only: rejected. It does not satisfy the per-subsystem design-note duty.

## Open questions

None. Both scope questions were answered before planning (coverage B, live keyless source A), and
the plan resolves every technical unknown above.
