# Contracts: Weather Tool

**Date**: 2026-11-19 | **Feature**: specs/008-weather-query-tool

The agent's model-facing surface is the tool registry: name, description and input schema become
the request's `tools`, and the handler's returned string becomes the tool result. This contract
covers that tool, its text output, the two outbound HTTP requests behind it, and the configuration
that can remove it. The dashboard HTTP API is unchanged: `GET /api/tools` already returns the live
registry and the trajectory's tool events, so the weather card appears there automatically.

## 1. Tool declaration

| Field | Value |
|-------|-------|
| name | `query_weather` |
| description | "Look up current weather and a short daily forecast (today plus the next three days) for a city. Returns temperature, conditions, humidity, wind and precipitation with units." |
| handler | `make_tools(conn, settings, client=None)` in `byo/tools/weather.py` |

### Input schema

~~~json
{
  "type": "object",
  "properties": {
    "place": {
      "type": "string",
      "description": "city name, optionally with region or country, e.g. 'Springfield, Illinois'"
    },
    "start": {
      "type": "string",
      "description": "ISO date (YYYY-MM-DD) to start from; default today in the place's time zone"
    },
    "end": {
      "type": "string",
      "description": "ISO date to end at; default the same day as start; at most three days after today"
    },
    "units": {
      "type": "string",
      "enum": ["metric", "imperial"],
      "description": "temperature, wind and precipitation units; default metric"
    }
  },
  "required": ["place"]
}
~~~

Behaviour rules:

- `place` is trimmed. Empty place → the configured default place; still empty → `place not
  recognised` (the model can then ask).
- Omitting `start`/`end` yields today through today + 3 (four daily rows including today).
- `start` without `end` is a single day. Both dates are place-local.
- Any value outside `[today, today + 3]`, or `start > end`, is `request out of range`.
- `units` may be omitted; an unknown value is refused with a readable argument error.
- Extra properties are not part of the contract; the registry reports an unknown argument as its
  usual argument-error text, which the model can correct on the next call.

## 2. Output text contract

Shape (metric example; imperial swaps the labels):

~~~text
Weather for <Name, admin1, country> (<timezone>) — read <YYYY-MM-DD HH:MM> local.
Now: <temp> °C (feels <apparent> °C), <condition>, humidity <n>%, wind <speed> km/h from <compass>, precipitation <n> mm.
Daily:
<YYYY-MM-DD>: <condition>, <low>–<high> °C, rain chance <n>%, <precip> mm
…
Weather data by Open-Meteo.com
~~~

Guarantees:

- The header states the resolved place (so a wrong pick is visible), its IANA time zone, and the
  reading time in that zone.
- "Now" carries temperature, apparent temperature, condition, humidity, wind speed and direction,
  and precipitation, each with a unit.
- One daily line per requested day, ascending, with the explicit ISO date; there are at most four.
- The block ends with the provider attribution line required by Open-Meteo's terms.
- No credential, header value or provider URL appears in the output.
- The block is bounded by construction and stays under 2000 characters for a four-day range.
- The tool returns text only; it never returns JSON, HTML or a dict.

## 3. Failure text contract

Every failure is a single string beginning with `Error: `. The registry's existing rule then
marks the call `ok = false` in the trajectory and the dashboard, and the loop hands the text to
the model.

| Category | Trigger | Guaranteed content |
|----------|---------|--------------------|
| `place not recognised` | no candidates; empty place with no default | the name asked for; an instruction to ask for a clearer place |
| `place ambiguous` | several candidates and none dominates | up to five "Name, admin1, country" candidates, so the model can ask which |
| `request out of range` | unparseable date, start > end, outside today..today+3 | the supported window as explicit dates |
| `service unavailable` | timeout, DNS/URL error, HTTP 429 or 5xx | the fact that no answer arrived and a retry hint |
| `data unavailable` | HTTP 200 with non-JSON, wrong root type, missing/misaligned fields | the fact that the reading is incomplete for this place |

Never: an exception escaping for an expected failure; a fabricated reading; a partial report
rendered as if complete; a default city substituted silently.

## 4. Upstream contract (outbound)

No credential. Both requests carry a `User-Agent` naming this build, the configured timeout, and a
200 KB read cap.

### 4.1 Geocoding

`GET https://geocoding-api.open-meteo.com/v1/search`

| Parameter | Value |
|-----------|-------|
| name | the cleaned place (first comma segment when a hint is present) |
| count | 8 |
| language | `zh` when the query contains CJK characters, else `en` |
| format | `json` |

Response fields consumed: `results[].name`, `admin1`, `admin2`, `country`, `country_code`,
`latitude`, `longitude`, `timezone`, `population`, `feature_code`. A missing `results` key is
an empty candidate list, not an error.

### 4.2 Forecast

`GET https://api.open-meteo.com/v1/forecast`

| Parameter | Value |
|-----------|-------|
| latitude, longitude | from the resolved place |
| current | `temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m,precipitation` |
| daily | `weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum` |
| timezone | `auto` |
| forecast_days | 4 |
| temperature_unit | `celsius` or `fahrenheit` |
| wind_speed_unit | `kmh` or `mph` |
| precipitation_unit | `mm` or `inch` |

Response fields consumed: `timezone`, `timezone_abbreviation`, `current_units`, `daily_units`,
`current.{time,temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m,precipitation}`,
`daily.time[]`, `daily.weather_code[]`, `daily.temperature_2m_max[]`,
`daily.temperature_2m_min[]`, `daily.precipitation_probability_max[]`,
`daily.precipitation_sum[]`. Daily arrays must share one length ≥ 1 and must start on the
requested start date; the `current_units` / `daily_units` metadata must denote the requested
system (°C vs °F, km/h vs mp/h or mph, mm vs inch). Any violation is reported as `data
unavailable`.

### 4.3 Status handling

| Upstream result | Tool outcome |
|-----------------|--------------|
| 200 + valid JSON + complete fields | rendered report |
| 200 + JSON but missing fields / misaligned arrays / non-JSON | `data unavailable` |
| 429 (rate limited) | `service unavailable` + retry hint |
| 5xx | `service unavailable` |
| timeout / DNS / TLS / connection error | `service unavailable` |

## 5. Cache and duplicate-call semantics

- Geocoding: key (normalized query, language), TTL 1 hour.
- Forecast: key (lat4, lon4, units), TTL 60 seconds.
- At most 128 entries; oldest evicted first; failures never cached.
- A second question about the same place and units in one turn hits the cache, so one turn makes
  at most two upstream calls per distinct place (geocode + forecast), and none for a cached place.

## 6. Configuration contract

| Variable | Default | Meaning |
|----------|---------|---------|
| `BYO_WEATHER_ENABLED` | `true` | false removes the tool from the registry entirely |
| `BYO_WEATHER_TIMEOUT_SECONDS` | `5` | per-request timeout; clamped to 1–30 |
| `BYO_WEATHER_DEFAULT_PLACE` | empty | used when a request names no place |

Loaded once by `byo.config.load_settings`; no other module reads the environment. The example
environment file documents all three, and `test_env_example.py` keeps the documented set equal to
the consumed set.

## 7. Record and surface contract

- The loop writes `tool_start` and `tool` records for every call (name, arguments, output, ok,
  duration), redacted at the trajectory sink. No new event type is introduced.
- The dashboard's `GET /api/tools` returns the weather tool in `tools` (live registry) and its
  calls in `results` (trajectory), so the Tools view needs no code change.
- A disabled tool is absent from the registry, the model's schema list and the Tools view alike.

## 8. Non-goals

- No history, alerts, air quality, hourly detail, maps or batch queries.
- No persistence of weather data, no schema change, no new dashboard endpoint.
- No credential support in this contract; a future credentialed source is out of scope for
  `008` and would be a plan-level decision with its own secret handling.
