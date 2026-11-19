# Feature Specification: Weather Query Tool

**Feature Branch**: `008-weather-query-tool`

**Created**: 2026-11-19

**Status**: Draft

**Input**: User description: "增加一个 weather 查询的 tool"

## Clarifications

### Session 2026-11-19

- Q: 预报覆盖范围是只做当前天气，还是也覆盖未来几天？ → A: **B** — 当前天气 + 未来 3 天逐日预报（今天 + 明天、后天、第三天）。
- Q: 天气数据来源是真实联网服务还是内置离线数据？ → A: **A** — 公共免费天气服务，无需 API key、无需任何凭据，只需网络；默认测试套件仍使用录制数据离线运行。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask for the current weather in a place (Priority: P1)

A person asks the agent, in whatever language they type, about the weather right now in a named
place — "上海今天天气怎么样？" or "is it raining in Lisbon?". The agent recognises this as a
weather request, resolves the place, calls the new weather tool, and answers with the current
conditions: temperature and what it feels like, the sky condition, humidity, wind and
precipitation, the place it used, and when that reading is valid. The answer is in the person's
language, with units stated. A follow-up ("要带伞吗？") can reuse the same reading within the
turn instead of fetching the same place twice.

**Why this priority**: This is the smallest slice that makes the tool worth existing — the
person asks about the weather and gets a truthful, sourced answer. Everything else (another
day, failure handling) extends or hardens this one journey.

**Independent Test**: Offline, with a scripted model and a recorded weather reading, drive one
turn that asks for a named place's current weather; verify one weather tool call with the
resolved place, the recorded values reaching the model, and a reply that states temperature,
sky condition and validity time, with units.

**Acceptance Scenarios**:

1. **Given** a resolvable place and a recorded current reading, **When** the person asks for the weather there, **Then** the reply states at least temperature, sky condition, humidity, wind and precipitation, names the place used, and states when the reading was taken.
2. **Given** a person who asks in Chinese, **When** the answer is produced, **Then** the reply is in Chinese and every number carries its unit (e.g. °C, km/h, mm).
3. **Given** one turn that asks about one place, **When** the agent answers, **Then** that place is fetched at most once in the turn (repeated questions reuse the same reading).
4. **Given** a place name that matches a known city, **When** the tool resolves it, **Then** it resolves to a specific city-level place and states the resolved name and its local time zone.

---

### User Story 2 - Ask about another day or a short range (Priority: P2)

The person asks about the near future — "明天会下雨吗？", "这周末的天气怎么样？". The agent
calls the weather tool with the requested day or range and answers with one line per day
(condition, high/low, precipitation chance), highlighting the days that matter. If the
requested day is outside what the tool covers, the reply says so plainly and states the range
the tool can answer for, rather than inventing a forecast.

**Why this priority**: Most real weather questions are prospective, and a current-conditions
tool alone disappoints. It ranks below P1 because the P1 journey is still useful on its own,
and above P3 because it is the second thing people ask.

**Independent Test**: Offline, with recorded daily forecasts for today and the next three days,
drive a turn that asks about tomorrow and a turn that asks about a day beyond the three-day
horizon; verify the tool received the intended dates, the reply lists per-day values for the
covered case, and the out-of-range case states the supported range without fabricating values.

**Acceptance Scenarios**:

1. **Given** recorded forecasts for the next days, **When** the person asks about tomorrow, **Then** the reply gives tomorrow's condition, high/low and precipitation chance for the resolved place.
2. **Given** a request for a range of days within coverage, **When** the agent answers, **Then** the reply covers each day in the range, in order, one line per day.
3. **Given** a request for a day before today or beyond the three-day horizon, **When** the agent answers, **Then** the reply states the supported range (today plus the next three days) and does not present a forecast for that day.
4. **Given** a relative expression ("tomorrow", "this weekend"), **When** it is resolved, **Then** it is resolved against the resolved place's local date, and the reply makes clear which dates were used.

---

### User Story 3 - Failures are honest and every call is visible (Priority: P3)

The place is ambiguous, unknown, the public weather source is slow, unreachable, rate-limits
the deployment, or returns malformed data. In every one of these cases the tool returns a
plain, readable reason to the agent, the turn continues, and the person gets an explanation
instead of a hang or an invented temperature. Every call — successful or not — appears in the run's trajectory
and in the dashboard's Tools view, so a maintainer can see exactly what was asked and what came
back.

**Why this priority**: This is what keeps the tool trustworthy. It is P3 only because it
hardens the first two journeys; it is non-negotiable for shipping.

**Independent Test**: Offline scripted scenarios for an ambiguous place, an unknown place, a
service timeout, a rate-limited response and a malformed payload; verify each turn completes,
the model receives the categorised error text, no exception escapes, and the trajectory records
the failed call.

**Acceptance Scenarios**:

1. **Given** a place name that matches more than one place, **When** the agent needs to answer, **Then** the reply asks which place was meant and names the candidates, instead of silently picking one.
2. **Given** a name that matches no place, **When** the tool runs, **Then** it returns a "place not recognised" reason and the reply asks for a clearer place.
3. **Given** the weather source does not answer within the allowed wait, **When** the turn continues, **Then** the reply says the weather data is temporarily unavailable and offers to retry, and the turn still ends normally.
4. **Given** the public service rate-limits the deployment, **When** the tool is called, **Then** it reports "service unavailable" (not a crash) and the reply offers to retry later.
5. **Given** any weather call, **When** the call finishes, **Then** the trajectory records its name, arguments, outcome, success flag and duration, and the dashboard's Tools view lists the weather tool in Available and the call in Results.

---

### Edge Cases

- The person asks without a place ("这里天气怎么样？"): the agent uses a configured default place if one exists, otherwise it asks for a place rather than guessing from an address or network origin.
- The person asks about a place they already asked about in the same turn: the same reading is reused; no duplicate call.
- An upstream response is empty, malformed or missing fields: the tool reports "weather data unavailable for this place" instead of returning partial garbage.
- The person asks for a day in the past: the reply says historical weather is not supported rather than substituting today's reading.
- The person asks for imperial units or another language: units and language follow the request; the default is metric and the person's language.
- The upstream data is older than the allowed freshness window: the reply states the reading time and flags it as not current.
- The same place name exists in several countries and the person names none: treated as ambiguous (see User Story 3).
- A turn makes several weather calls (e.g. two cities): each place is fetched once; failures are independent.
- The network is unavailable entirely: the tool fails with the "service unavailable" category; the conversation continues.
- The keyless public service rate-limits or blocks the deployment: the tool reports "service unavailable" with a retry hint, and later calls in the same turn are not spammed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The agent MUST expose exactly one new capability, a weather query tool, callable from any surface (terminal and dashboard chat) like the existing tools, with a name, a description and an explicit input contract visible to the model.
- **FR-002**: The tool MUST accept a place (city-level name; required), an optional date or date range, and an optional unit preference, and MUST reject an empty place with a readable reason.
- **FR-003**: The tool MUST resolve a place name to one city-level location, report the resolved name, region/country and the location's local time zone, and MUST NOT silently choose when a name is ambiguous.
- **FR-004**: For the current day, the tool MUST return the current conditions: temperature, apparent temperature, sky condition, humidity, wind, precipitation and the time those values are valid for.
- **FR-005**: The tool MUST cover today plus the next three days: current conditions for today, and a daily forecast for each of tomorrow, the day after, and the third day. Each daily entry MUST include the condition, high/low temperature and precipitation chance, and the reply MUST state this three-day horizon whenever a request falls outside it.
- **FR-006**: The weather data MUST come from a live public weather service that requires no API key or credential, reached over the network; a fresh checkout MUST work with network access alone. Recorded data is used only as test fixtures in the offline suite.
- **FR-007**: Dates and date ranges MUST be interpreted in the resolved place's local date; relative expressions ("today", "tomorrow", "this weekend") MUST be resolved to explicit dates and those dates MUST appear in the reply.
- **FR-008**: The tool MUST enforce a bounded wait for any external answer and MUST convert every failure into model-readable text carrying a reason category: place not recognised, place ambiguous, data unavailable, service unavailable (including rate limiting), request out of range.
- **FR-009**: Any weather failure MUST NOT raise out of the tool, MUST NOT hang the turn, and MUST NOT cause the agent to present invented weather values.
- **FR-010**: Units MUST default to metric and MUST be requestable as imperial; every number in the reply MUST carry its unit.
- **FR-011**: Each weather call MUST be recorded in the run's trajectory (name, arguments, outcome, success flag, duration) and MUST appear in the dashboard's Tools view — the tool in its Available catalog with its input contract, the call in Results.
- **FR-012**: The tool MUST be enabled or disabled through configuration, and default to enabled once shipped; enablement MUST NOT be a hardcoded literal in the control path.
- **FR-013**: The shipped tool MUST NOT require or read any provider credential. If a credentialed source is added later, that credential MUST come from the environment or secret store, MUST never appear in source, replies, traces, logs or fixtures, and its absence MUST be reported as a configuration problem rather than a crash.
- **FR-014**: Repeated requests for the same place within one turn (or within a short freshness window) MUST NOT trigger duplicate external calls.
- **FR-015**: The default test suite MUST cover all acceptance scenarios of this feature offline against recorded or synthetic weather data, with no network and no credentials, and MUST pass.
- **FR-016**: Because the tool's description and output shape influence model behaviour, the change MUST ship with an eval delta (baseline vs post-change scores and the cases that moved) per the project constitution.

### Key Entities *(include if feature involves data)*

- **Place**: the location a query is about — resolved city-level name, region/country, local time zone, and the coordinates the data source uses; ambiguous names yield candidates rather than a single place.
- **Weather reading**: one observation or forecast day for a place — the values (temperature, apparent temperature, condition, humidity, wind, precipitation), the valid time or date, the unit system, and the source and freshness of the data.
- **Weather query**: one request to the tool — the place as given, the resolved place, the requested dates, the requested units, and the outcome (values or reason category).
- **Tool call record**: the trajectory entry for one call — name, arguments, outcome, success flag and duration; also what the dashboard Tools view renders.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of the pinned offline scenarios for a resolvable place, the reply's weather values match the recorded source values, and none is invented or altered.
- **SC-002**: A weather question on the terminal or in the dashboard chat is answered within 5 seconds (p95) when the data source responds, including the tool call.
- **SC-003**: In 100% of the failure scenarios (ambiguous, unknown, timeout, rate-limited, malformed payload, out-of-range date), the person receives a plain explanation and the turn completes; zero unhandled exceptions in the test suite.
- **SC-004**: Every weather call appears in the trajectory and in the dashboard Tools view; a reviewer can read the arguments and outcome of 100% of calls from the trajectory alone.
- **SC-005**: No route is found by which a credential can reach a reply, trace line, log line or committed fixture; 100% of redaction checks pass.
- **SC-006**: The default test command passes offline with no network and no credentials, and the change lowers no existing eval score.
- **SC-007**: In 100% of offline forecast scenarios the reply covers today and each of the next three days, and any request outside that window is answered with the three-day horizon and no fabricated values.
- **SC-008**: The weather tool's card appears in the dashboard's Available catalog after one page load, and its description and input contract match what the model is offered in 100% of checks.

## Out of Scope

- Weather alerts, push notifications and scheduled briefings.
- Historical weather, climate trends, seasonal outlooks and long-range forecasting.
- Hourly forecasts and any forecast beyond the three-day daily horizon.
- Extended indices (air quality, UV, pollen, tides) — the tool answers the everyday weather question only.
- Maps, radar layers and any new dashboard view; the tool reuses the existing Tools view.
- Batch queries, multi-place comparison, and route or commute weather.
- New memory types or persistence for weather data; any caching stays in-memory and short-lived.

## Assumptions

- The tool is agent-facing only: people reach it by talking to the agent, not through a standalone service endpoint.
- Place resolution to city level (name, region/country, time zone) is sufficient; street-level accuracy is not required.
- The default unit system is metric, with imperial available on request; the reply language follows the person's language.
- "Today" and relative date expressions are evaluated in the resolved place's local time zone.
- The new tool follows the existing tool pattern: declared description and input contract, a handler returning human-readable text, and errors converted to text — so it lands in both terminal and dashboard paths without a second implementation.
- Weather data is read-only and not persisted; at most a short-lived in-memory cache is kept to avoid duplicate calls in a turn.
- The dashboard's Tools view already enumerates tools automatically; the new tool needs no dashboard code change beyond whatever the existing discovery mechanism requires.
- The default source is keyless, so no credential is configured for the shipped tool; if a credentialed source is introduced later, the deployment supplies it through the environment and a missing value is a configuration error, not a startup crash.
- The public service is rate-limited and best-effort: the tool keeps per-turn usage conservative and degrades to an honest "service unavailable" when the limit is hit.
