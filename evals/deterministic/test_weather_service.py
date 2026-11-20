"""Weather service: resolution, dates, units, failures and the two caches."""

from __future__ import annotations

import copy
from datetime import UTC, datetime

import pytest
from weather_fakes import FakeClient, FakeClock, load_fixture

from byo.weather.client import BadData, ServiceUnavailable
from byo.weather.service import (
    AMBIGUOUS,
    CACHE_MAX,
    DATA_UNAVAILABLE,
    FORECAST_TTL,
    GEOCODE_TTL,
    NOT_RECOGNISED,
    OUT_OF_RANGE,
    SERVICE_UNAVAILABLE,
    WeatherFailure,
    WeatherService,
    compass,
    condition_for,
)


def build(geocode="geocode-shanghai", forecast="forecast-metric", **kwargs):
    clock = FakeClock()
    client = FakeClient(
        load_fixture(geocode) if isinstance(geocode, str) else geocode,
        load_fixture(forecast) if isinstance(forecast, str) else forecast,
    )
    return WeatherService(client, clock=clock, **kwargs), client, clock


def test_known_and_unknown_weather_codes():
    assert condition_for(0) == "clear sky"
    assert condition_for(95) == "thunderstorm"
    assert condition_for(1234) == "WMO code 1234"


def test_compass_points_the_way():
    assert compass(0) == "N"
    assert compass(306) == "NW"
    assert compass(260) == "W"
    assert compass(359) == "N"


def test_a_dominant_place_resolves():
    service, client, _ = build()
    report = service.report(place="Shanghai")
    assert report.place.name == "Shanghai"
    assert report.place.population == 24874500
    assert report.timezone == "Asia/Shanghai"
    assert "language=en" in client.calls[0]


def test_a_cjk_query_asks_for_chinese_names():
    service, client, _ = build(geocode="geocode-shanghai-zh")
    report = service.report(place="上海")
    assert report.place.name == "上海"
    assert "language=zh" in client.calls[0]


def test_springfield_is_ambiguous_not_guessed():
    service, _, _ = build(geocode="geocode-springfield")
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Springfield")
    failure = caught.value
    assert failure.category == AMBIGUOUS
    assert 1 <= len(failure.candidates) <= 5
    assert failure.candidates[0] == "Springfield, Missouri, United States"
    assert any("Illinois" in candidate for candidate in failure.candidates)


def test_a_region_hint_picks_the_named_springfield():
    service, _, _ = build(geocode="geocode-springfield")
    report = service.report(place="Springfield, Illinois")
    assert report.place.admin1 == "Illinois"


def test_an_unknown_place_is_refused():
    service, _, _ = build(geocode="geocode-empty")
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Xyzzy Town")
    assert caught.value.category == NOT_RECOGNISED


def test_an_empty_place_uses_the_configured_default():
    service, client, _ = build(default_place="Shanghai")
    report = service.report()
    assert report.place.name == "Shanghai"
    assert "name=Shanghai" in client.calls[0]


def test_an_empty_place_without_a_default_is_refused():
    service, _, _ = build()
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="  ")
    assert caught.value.category == NOT_RECOGNISED


def test_the_default_range_is_today_through_three_days():
    service, _, _ = build()
    report = service.report(place="Shanghai")
    assert [day.date for day in report.daily] == [
        "2026-11-19",
        "2026-11-20",
        "2026-11-21",
        "2026-11-22",
    ]
    assert report.current.temperature == 10.9
    assert report.current.condition == "clear sky"
    assert report.current.wind_compass == "NW"


def test_a_single_start_day_is_one_line():
    service, _, _ = build()
    report = service.report(place="Shanghai", start="2026-11-20")
    assert [day.date for day in report.daily] == ["2026-11-20"]


def test_a_range_keeps_order():
    service, _, _ = build()
    report = service.report(place="Shanghai", start="2026-11-20", end="2026-11-21")
    assert [day.date for day in report.daily] == ["2026-11-20", "2026-11-21"]


@pytest.mark.parametrize("start", ["2026-11-18", "2026-11-30"])
def test_dates_outside_the_window_are_refused(start):
    service, _, _ = build()
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai", start=start)
    failure = caught.value
    assert failure.category == OUT_OF_RANGE
    assert "today..today+3" in failure.message
    assert "2026-11-19..2026-11-22" in failure.message


def test_start_after_end_is_refused():
    service, _, _ = build()
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai", start="2026-11-21", end="2026-11-20")
    assert caught.value.category == OUT_OF_RANGE


def test_a_non_iso_date_is_refused():
    service, _, _ = build()
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai", start="tomorrow-ish")
    assert caught.value.category == OUT_OF_RANGE
    assert "not an ISO date" in caught.value.message


def test_a_unit_mismatch_is_data_unavailable():
    service, _, _ = build(forecast="forecast-unit-mismatch")
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai", units="metric")
    assert caught.value.category == DATA_UNAVAILABLE


def test_a_missing_daily_array_is_data_unavailable():
    service, _, _ = build(forecast="forecast-malformed")
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai")
    assert caught.value.category == DATA_UNAVAILABLE


def test_a_timeout_is_service_unavailable_and_retryable():
    clock = FakeClock()
    service = WeatherService(
        FakeClient(error=ServiceUnavailable("HTTP 429")), clock=clock
    )
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai")
    assert caught.value.category == SERVICE_UNAVAILABLE
    assert caught.value.retryable is True


def test_transport_bad_data_is_data_unavailable():
    clock = FakeClock()
    service = WeatherService(FakeClient(error=BadData("not json")), clock=clock)
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai")
    assert caught.value.category == DATA_UNAVAILABLE


def test_unknown_units_is_an_argument_error():
    service, _, _ = build()
    with pytest.raises(ValueError):
        service.report(place="Shanghai", units="kelvin")


def test_a_second_question_uses_the_cache():
    service, client, _ = build()
    service.report(place="Shanghai")
    service.report(place="Shanghai")
    assert client.geocode_calls() == 1
    assert client.forecast_calls() == 1
    assert len(client.calls) == 2


def test_the_forecast_cache_expires_after_a_minute():
    service, client, clock = build()
    service.report(place="Shanghai")
    clock.advance(FORECAST_TTL + 1)
    service.report(place="Shanghai")
    assert client.geocode_calls() == 1
    assert client.forecast_calls() == 2


def test_the_geocode_cache_expires_after_an_hour():
    service, client, clock = build()
    service.report(place="Shanghai")
    clock.advance(GEOCODE_TTL + 1)
    service.report(place="Shanghai")
    assert client.geocode_calls() == 2
    assert client.forecast_calls() == 2


def test_failures_are_not_cached():
    service, client, _ = build()
    client.error = ServiceUnavailable("boom")
    with pytest.raises(WeatherFailure):
        service.report(place="Shanghai")
    client.error = None
    report = service.report(place="Shanghai")
    assert report.place.name == "Shanghai"
    assert client.geocode_calls() == 2


def test_the_cache_evicts_the_oldest_entry_at_the_cap():
    service, _, _ = build()
    for index in range(CACHE_MAX):
        service._cached(("k", index), 3600, lambda index=index: {"i": index})
    service._cached(("k", CACHE_MAX), 3600, lambda: {"i": "new"})
    assert len(service._cache) == CACHE_MAX
    assert ("k", CACHE_MAX) in service._cache


def test_now_reports_the_clock():
    service, _, clock = build()
    assert service.now() is clock.now


def test_a_country_code_hint_resolves():
    service, _, _ = build()
    report = service.report(place="Shanghai, cn")
    assert report.place.name == "Shanghai"
    assert report.place.country_code == "CN"


def test_a_region_hint_matching_nothing_is_refused():
    service, _, _ = build(geocode="geocode-springfield")
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Springfield, Texas")
    assert caught.value.category == NOT_RECOGNISED
    assert "in the region you named" in caught.value.message


def test_non_list_results_are_data_unavailable():
    service, _, _ = build(geocode={"results": {"name": "Shanghai"}})
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai")
    assert caught.value.category == DATA_UNAVAILABLE


def test_an_unknown_timezone_falls_back_to_utc():
    geocode = load_fixture("geocode-shanghai")
    for result in geocode["results"]:
        result["timezone"] = "Bogus/Zone"
    clock = FakeClock(datetime(2026, 11, 19, 23, 0, tzinfo=UTC))
    client = FakeClient(geocode, load_fixture("forecast-metric"))
    service = WeatherService(client, clock=clock)
    report = service.report(place="Shanghai")
    # Asia/Shanghai would call it the 20th; the UTC fallback keeps it the 19th.
    assert report.daily[0].date == "2026-11-19"


def mutated_forecast(mutate):
    payload = copy.deepcopy(load_fixture("forecast-metric"))
    mutate(payload)
    return payload


def test_missing_current_block_is_data_unavailable():
    forecast = mutated_forecast(lambda p: p.pop("current"))
    service, _, _ = build(forecast=forecast)
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai")
    assert caught.value.category == DATA_UNAVAILABLE


def test_empty_daily_times_are_data_unavailable():
    forecast = mutated_forecast(lambda p: p["daily"].update(time=[]))
    service, _, _ = build(forecast=forecast)
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai")
    assert caught.value.category == DATA_UNAVAILABLE


def test_a_day_missing_from_the_times_is_data_unavailable():
    def drop(payload):
        daily = payload["daily"]
        index = daily["time"].index("2026-11-20")
        for values in daily.values():
            if isinstance(values, list):
                values.pop(index)

    service, _, _ = build(forecast=mutated_forecast(drop))
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai", start="2026-11-20")
    assert caught.value.category == DATA_UNAVAILABLE


def test_descending_times_are_data_unavailable():
    def reverse(payload):
        daily = payload["daily"]
        for key, values in daily.items():
            if isinstance(values, list):
                daily[key] = values[::-1]

    service, _, _ = build(forecast=mutated_forecast(reverse))
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai", start="2026-11-19", end="2026-11-22")
    assert caught.value.category == DATA_UNAVAILABLE


def test_a_missing_timezone_is_data_unavailable():
    geocode = load_fixture("geocode-shanghai")
    for result in geocode["results"]:
        result["timezone"] = ""
    forecast = mutated_forecast(lambda p: p.pop("timezone"))
    service, _, _ = build(geocode=geocode, forecast=forecast)
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai")
    assert caught.value.category == DATA_UNAVAILABLE


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(current_units="celsius"),
        lambda p: p["current_units"].update(apparent_temperature="°F"),
        lambda p: p["current_units"].update(wind_speed_10m="mph"),
        lambda p: p["current_units"].update(precipitation="inch"),
        lambda p: p["daily_units"].update(temperature_2m_max="°F"),
        lambda p: p["daily_units"].update(temperature_2m_min="°F"),
        lambda p: p["daily_units"].update(precipitation_sum="inch"),
    ],
    ids=[
        "non-dict-units",
        "apparent-temperature",
        "wind-speed",
        "precipitation",
        "daily-max",
        "daily-min",
        "daily-precipitation",
    ],
)
def test_unit_mismatches_are_data_unavailable(mutate):
    service, _, _ = build(forecast=mutated_forecast(mutate))
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai")
    assert caught.value.category == DATA_UNAVAILABLE


def test_boolean_numbers_are_data_unavailable():
    forecast = mutated_forecast(lambda p: p["current"].update(temperature_2m=True))
    service, _, _ = build(forecast=forecast)
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai")
    assert caught.value.category == DATA_UNAVAILABLE


def test_a_blank_reading_time_is_data_unavailable():
    forecast = mutated_forecast(lambda p: p["current"].update(time=""))
    service, _, _ = build(forecast=forecast)
    with pytest.raises(WeatherFailure) as caught:
        service.report(place="Shanghai")
    assert caught.value.category == DATA_UNAVAILABLE
