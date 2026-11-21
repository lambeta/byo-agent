# Quickstart Validation: Weather Query Tool

**Date**: 2026-11-19 | **Feature**: specs/008-weather-query-tool

A runnable guide for proving the feature end to end. Shapes and guarantees are in
[data-model.md](data-model.md) and [contracts/weather-tool.md](contracts/weather-tool.md); this
file only lists commands and expected outcomes.

## Prerequisites

- A Python virtual environment with the project installed: `.venv/bin/python` exists.
- The default validation path needs **no network and no credentials**: the weather tests use a
  fake JSON client and recorded fixtures, and the model is the scripted adapter.
- The optional live checks in sections 3 and 5 need network access to Open-Meteo; section 3 also
  needs a real `BYO_API_KEY` because the CLI chat calls a model.

## 1. The offline suite

~~~bash
make eval
make lint
~~~

Expected: the deterministic suite passes. Baseline before this feature was **277 tests**; the
post-change run includes the new `test_weather_client.py`, `test_weather_service.py` and
`test_weather_tool.py` cases plus the updated contract tests, and reports a higher count. Lint is
clean.

Run just the weather layer while developing:

~~~bash
.venv/bin/python -m pytest evals/deterministic/test_weather_client.py -v
.venv/bin/python -m pytest evals/deterministic/test_weather_service.py -v
.venv/bin/python -m pytest evals/deterministic/test_weather_tool.py -v
~~~

Expected: transport failures typed (timeout, 429, 5xx, non-JSON), resolution refusing to guess,
date bounds enforced, unit labels correct, cache dedupe proven, and a scripted turn whose
trajectory records `query_weather` with `ok: true`.

## 2. Prove the tool set is exactly seven

~~~bash
.venv/bin/python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory

from byo.config import load_settings
from byo.db import connect
from byo.memory import Memory
from byo.tools import build_registry

with TemporaryDirectory() as tmp:
    home = Path(tmp)
    settings = load_settings(env={"BYO_HOME": str(home)}, home=home)
    conn = connect(home)
    registry = build_registry(conn, settings, memory=None)
    print(registry.names())
    with_memory = build_registry(conn, settings, memory=Memory(conn, settings, None))
    print(with_memory.names())
PY
~~~

Expected:

- Without memory: `create_event, list_events, save_note, send_message, query_weather` (5).
- With memory: the same plus `manage_memory, update_persona` (7), which is what the closed-set
  test asserts.

## 3. Live CLI smoke (optional, network + model credential)

~~~bash
export BYO_API_KEY=...            # your existing key
.venv/bin/python -m byo
~~~

Then ask, in sequence:

1. `上海今天天气怎么样？`
2. `明天会下雨吗？`
3. `Springfield 的天气呢？`
4. `下个月 31 号的天气？`

Expected in the terminal:

1. A tool line `tool · query_weather(place=上海) → Weather for 上海, 上海市, 中国 (Asia/Shanghai) …`
   and a reply with the values, units and reading time.
2. A call for tomorrow's date only; the reply names the date and the place-local time zone.
3. The agent asks **which** Springfield (Missouri, Illinois, …) instead of answering for one.
4. The reply says the request is outside the supported window (today + 3 days); no invented
   forecast.

The reply language follows the language you typed; the tool text stays English and the model
translates. The attribution line "Weather data by Open-Meteo.com" appears in the tool output.

## 4. Dashboard Tools view

Start the dashboard against a scratch home (a dummy key is enough to boot; only chat needs a real
one):

~~~bash
SCRATCH_HOME=$(mktemp -d)
BYO_HOME="$SCRATCH_HOME" BYO_API_KEY=test BYO_PORT=7788 .venv/bin/python -m byo dashboard
~~~

Open http://127.0.0.1:7788/#tools.

Expected:

- **Available** shows a `query_weather` card whose description and input schema match
  [contracts/weather-tool.md](contracts/weather-tool.md), and six other cards.
- **Results** shows one row per recorded weather call (tool, ok/error, duration, output preview,
  when) once a turn has run — the offline dashboard test asserts the same payload.
- The Overview map's Tools node reports seven tools.

Then prove the switch is real:

~~~bash
BYO_HOME="$SCRATCH_HOME" BYO_API_KEY=test BYO_PORT=7789 \
  BYO_WEATHER_ENABLED=false .venv/bin/python -m byo dashboard
~~~

Expected: the Tools view lists six tools and no `query_weather` card; a weather question cannot
call it because the model is not offered the schema.

## 5. Failure drills

| Scenario | How | Expected |
|----------|-----|----------|
| Unknown place | Ask for `Xyzzy Town weather` | `Error: place not recognised` reaches the model; the reply asks for a clearer city; the turn completes |
| Ambiguous place | Ask for `Springfield weather` | Candidates are listed; the reply asks which one; no temperature is presented |
| Out-of-range date | Ask for a date more than three days ahead | `Error: request out of range` states today..today+3; no fabricated forecast |
| Empty place, no default | Trigger `query_weather` with `place ""` (offline test) | Readable refusal asking for a city |
| Default place | Set `BYO_WEATHER_DEFAULT_PLACE=Shanghai` and ask `这里天气怎么样？` | The tool resolves Shanghai and says so |
| Upstream down | Run the offline timeout fixture (or disconnect the network for a live run) | `Error: service unavailable` after the built-in retry, telling the model not to call again this turn; the turn continues |
| Rate limited | 429 fixture | Same `service unavailable` category; no crash |
| Disabled | `BYO_WEATHER_ENABLED=false` | Tool absent from registry, model schema list and Tools view |

## 6. Trajectory record

~~~bash
grep '"tool": "query_weather"' "$SCRATCH_HOME"/trajectories/*.jsonl | tail -3
~~~

Expected: one `tool_start` and one `tool` record per call, with `args` (place/start/end/units),
`output`, `ok`, `call_id` and `duration_ms`; failures carry `ok: false` and the category text.
The output contains no credential, URL header or secret; the attribution line is present.

## 7. Upstream shape check (optional)

Confirm the provider still answers in the shape the fixtures record:

~~~bash
curl -s 'https://geocoding-api.open-meteo.com/v1/search?name=Shanghai&count=8&language=en&format=json' | head -c 600
curl -s 'https://api.open-meteo.com/v1/forecast?latitude=31.22222&longitude=121.45806&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m,precipitation&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum&timezone=auto&forecast_days=4' | head -c 600
~~~

Expected: a `results` array with `name/latitude/longitude/timezone/population` (the captured
fixture for Shanghai had three candidates), and a forecast body with `timezone`, `current`,
`current_units`, `daily` and `daily_units`. If either shape has changed, update the fixtures and
the mapping tests together.

## 8. Regression checks

~~~bash
grep -n "BYO_WEATHER" .env.example
grep -n "seven tools" README.md
.venv/bin/python -m pytest evals/deterministic/test_scope.py evals/deterministic/test_env_example.py -v
~~~

- `.env.example` documents exactly the three new knobs, and the env-example test passes.
- README says seven tools and mentions the weather tool.
- The dependency budget test still sees four runtime dependencies (stdlib only was used).
- No change to `GET /api/tools`, the Tools view script, the loop, the memory pipeline or the
  database schema; their existing tests stay green.

## Related artifacts

- [spec.md](spec.md) — acceptance scenarios and measurable outcomes.
- [plan.md](plan.md) — technical context, constitution check and source layout.
- [research.md](research.md) — decisions, live probes and rejected alternatives.
- [data-model.md](data-model.md) — entities, validation, error taxonomy, rendering.
- [contracts/weather-tool.md](contracts/weather-tool.md) — tool, text, upstream and config contracts.
