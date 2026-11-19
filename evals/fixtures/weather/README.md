# Weather fixtures

Recorded from Open-Meteo on 2026-11-19 from this checkout. They are replay data for the
offline weather tests; nothing here is fetched during the default test run.

| File | Source request | Why it exists |
|------|----------------|---------------|
| `geocode-shanghai.json` | `GET geocoding-api.open-meteo.com/v1/search?name=Shanghai&count=8&language=en&format=json` | Resolved place: first candidate has population 24874500, the rest have none, so the 5× dominance rule accepts it |
| `geocode-shanghai-zh.json` | same with `name=上海&language=zh` | CJK query: the service sends `language=zh` and the response names are Chinese |
| `geocode-springfield.json` | same with `name=Springfield` | Ambiguous place: 170188, 154341, 114394, 59680, 16808 — no candidate dominates |
| `geocode-empty.json` | same with `name=Xyzzy Town` | No results at all (body has no `results` key) |
| `forecast-metric.json` | `GET api.open-meteo.com/v1/forecast` for Shanghai, 4 days, default metric units | Current + daily shaping, °C/km/h/mm labels, timezone Asia/Shanghai, codes [3,1,0,3] |
| `forecast-imperial.json` | same for New York with `temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch` | Imperial labels; the provider spells mph as "mp/h" |
| `forecast-malformed.json` | derived from `forecast-metric.json` by removing `daily.temperature_2m_max` | A 200 response with a missing field must become "data unavailable" |
| `forecast-unit-mismatch.json` | derived from `forecast-metric.json` by relabelling the temperature units as °F while the request asked for metric | Unit metadata is validated, not trusted |

The two derived files are committed on purpose so the failure shapes are stable even if the live
service changes. When re-recording, keep the same file names and update the tests that assert
specific values (10.9 °C, 43.8 °F, the date arrays).
