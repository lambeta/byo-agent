# Data Model: Weather Query Tool

**Date**: 2026-11-19 | **Feature**: specs/008-weather-query-tool

All shapes below are in-process values. Nothing here is persisted: the database schema is
unchanged, and the only lasting record of a weather call is the trajectory's existing `tool`
event. The provider payloads that feed these shapes are documented in
[contracts/weather-tool.md](contracts/weather-tool.md).

## Entities

### Place

The location a query resolved to. Built from the geocoding response, never invented.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| name | str | `results[].name` | as the provider returned it (localized when the query is CJK) |
| admin1 | str | `results[].admin1` | region/state; may be empty |
| country | str | `results[].country` | may be empty |
| country_code | str | `results[].country_code` | two letters, used by comma hints |
| latitude | float | `results[].latitude` | rounded to 4 decimals for the cache key |
| longitude | float | `results[].longitude` | same |
| timezone | str | `results[].timezone` | IANA name; display only — dates come from the forecast response |
| population | int | `results[].population` | missing means 0; used only for ranking |

Validation: name non-empty; latitude in [-90, 90]; longitude in [-180, 180]. A missing or unknown
time zone falls back to UTC for the date window instead of dropping an otherwise usable place.

Display form: `Name, admin1, country` (empty parts dropped, comma-separated).

### WeatherQuery

One tool request after parsing.

| Field | Type | Required | Rule |
|-------|------|----------|------|
| place | str | yes | trimmed; if empty, the configured default place is used; if that is also empty → `place not recognised` |
| start | date or None | no | ISO date; default = today in the resolved place's time zone |
| end | date or None | no | ISO date; default = start; must be ≥ start |
| units | "metric" or "imperial" | no | default metric; any other value → readable argument error |

Validation order: clean place → resolve place → parse dates → check window → fetch → shape.
Dates are place-local; a query whose start is before the place-local today, whose end is after
today + 3, or whose start is after its end is refused as `request out of range` with the window
stated.

### CurrentReading

The "now" block from the forecast response, already unit-labelled by the provider.

| Field | Type | Provider field | Unit (metric / imperial) |
|-------|------|----------------|--------------------------|
| at | str | `current.time` | ISO local time |
| temperature | float | `current.temperature_2m` | °C / °F |
| apparent | float | `current.apparent_temperature` | °C / °F |
| humidity | int | `current.relative_humidity_2m` | % |
| weather_code | int | `current.weather_code` | WMO code |
| condition | str | mapped from the code | phrase |
| wind_speed | float | `current.wind_speed_10m` | km/h / mph |
| wind_direction | int | `current.wind_direction_10m` | degrees |
| wind_compass | str | derived | 16-point label ("NW") |
| precipitation | float | `current.precipitation` | mm / inch |

Validation: every value is coerced from the provider's number; a missing or non-numeric value
makes the whole response `data unavailable` (partial values are never rendered as if complete).
The provider's `current_units` is checked against the requested system: °C vs °F, km/h vs
mp/h (the provider's spelling of mph), mm vs inch. A mismatch is `data unavailable`, so a
printed label cannot disagree with its number.

### DailyForecast

One row per requested day, aligned by index with the provider's `daily.time` array.

| Field | Type | Provider field |
|-------|------|----------------|
| date | str (ISO date) | `daily.time[i]` |
| weather_code | int | `daily.weather_code[i]` |
| condition | str | mapped phrase |
| high | float | `daily.temperature_2m_max[i]` |
| low | float | `daily.temperature_2m_min[i]` |
| precip_chance | int | `daily.precipitation_probability_max[i]` |
| precip_sum | float | `daily.precipitation_sum[i]` |

Validation: the five arrays must exist, be lists, and share one length ≥ 1; an index where
`time` is present but any value is missing → `data unavailable`. Extra days beyond the requested
end are ignored; days before the requested start are not rendered.

### WeatherReport

The shaped value the tool renders.

| Field | Type | Notes |
|-------|------|-------|
| place | Place | resolved and displayed |
| units | "metric" | "imperial" | decides labels |
| timezone | str | from the forecast response (`timezone`), falling back to the place |
| current | CurrentReading | always present |
| daily | list[DailyForecast] | one entry per requested day, ascending |
| source | str | "Open-Meteo" |
| fetched_at | str | local ISO time of the response (for the "read at" phrase) |

Invariant: `daily[0].date == start` and `daily[-1].date == end`; any mismatch means the provider
returned a different window than asked, which is `data unavailable`.

### WeatherFailure

A refusal or upstream failure carried as data, then rendered as text.

| Field | Type | Notes |
|-------|------|-------|
| category | enum | `place not recognised` · `place ambiguous` · `data unavailable` · `service unavailable` · `request out of range` |
| message | str | one sentence the model can repeat or act on |
| candidates | list[str] | only for `place ambiguous`; up to five "Name, admin1, country" |
| retryable | bool | true only for `service unavailable` |

### CacheEntry

| Field | Type | Notes |
|-------|------|-------|
| key | tuple | geocode: (normalized query, language); forecast: (lat4, lon4, units) |
| value | dict | the provider payload needed to shape the report |
| stored_at | float (monotonic) | TTL check |
| ttl_seconds | int | geocode 3600, forecast 60 |

Rules: at most 128 entries; oldest is evicted first; failures are never cached; entries are
process-local and disappear on restart.

## Error taxonomy

| Condition | Category | Rendered text (shape) |
|-----------|----------|----------------------|
| geocoding returns no candidates | place not recognised | `Error: place not recognised: no city matched 'X'; ask for a clearer name.` |
| candidates exist but none dominates | place ambiguous | `Error: place ambiguous: did you mean Springfield, Missouri, United States; Springfield, Illinois, United States; …?` |
| place empty and no default | place not recognised | `Error: place not recognised: no place given and no default is configured; ask which city.` |
| date unparseable / order / outside window | request out of range | `Error: request out of range: '2026-11-30' is outside today..today+3 (2026-11-19..2026-11-22).` |
| HTTP 429, 5xx, timeout, DNS | service unavailable | `Error: service unavailable: the weather service did not answer; retry in a moment.` |
| 200 with missing/malformed fields | data unavailable | `Error: data unavailable: the weather service returned an incomplete reading for this place.` |
| argument type mismatch (registry) | (registry) | `Error: query_weather needs different arguments (…)` |

All of the tool's own failures are returned as strings beginning with `Error: `, so the registry
records `ok = false` and the loop continues.

## Rendering contract (text the model reads)

~~~text
Weather for Shanghai, Shanghai Municipality, China (Asia/Shanghai) — read 2026-11-19 14:15 local.
Now: 10.9 °C (feels 6.8 °C), clear sky, humidity 39%, wind 10.5 km/h from NW, precipitation 0.0 mm.
Daily:
2026-11-19: overcast, 4.0–10.9 °C, rain chance 0%, 0.0 mm
2026-11-20: mainly clear, 4.2–10.6 °C, rain chance 0%, 0.0 mm
2026-11-21: clear sky, 4.3–12.8 °C, rain chance 0%, 0.0 mm
2026-11-22: overcast, 6.0–14.8 °C, rain chance 0%, 0.0 mm
Weather data by Open-Meteo.com
~~~

Rules: header names the resolved place, its time zone and the read time; "Now" carries every
current field with its unit; one daily line per requested day with explicit ISO dates; the
attribution line is always last. The block is bounded by construction (≤ 4 daily lines) and stays
well under the trace sink's per-string cap.

Metric labels: °C, km/h, mm. Imperial labels: °F, mph, inch. The provider's
`current_units` / `daily_units` are validated against the requested system; a mismatch is
`data unavailable` rather than a relabelled number.

## Configuration and tool-set changes

| Knob | Default | Effect |
|------|---------|--------|
| `BYO_WEATHER_ENABLED` | true | false removes `query_weather` from the registry (and thus from the model and the Tools view) |
| `BYO_WEATHER_TIMEOUT_SECONDS` | 5 | per-request timeout, clamped 1–30 |
| `BYO_WEATHER_DEFAULT_PLACE` | (empty) | used when a request names no place |

Tool set: 5 tools without memory (`create_event`, `list_events`, `save_note`, `send_message`,
`query_weather`) and 7 with memory (`+ manage_memory`, `update_persona`). Existing
`test_tools.py` and `test_scope.py` expectations are updated in the same change.

## Lifecycle

1. Parse arguments; clean the place; apply the default place when needed.
2. Look up the geocode cache; on a miss, fetch candidates and store them for one hour.
3. Resolve to one Place or return `place not recognised` / `place ambiguous`.
4. Validate dates against the place-local window.
5. Look up the forecast cache by (lat4, lon4, units); on a miss, fetch and store for one minute.
6. Shape a WeatherReport; any missing field aborts to `data unavailable`.
7. Render the text block; return it. The loop records the tool event and shows it in the Tools
   view; the model turns the block into the person's language.
