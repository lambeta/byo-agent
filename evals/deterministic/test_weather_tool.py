"""The query_weather tool: schema, text, failures, registry and turn behaviour."""

from __future__ import annotations

import json
import threading
import urllib.request

from scripted import script, text, tool_call
from weather_fakes import FakeClient, FakeClock, load_fixture

from byo.app import Agent
from byo.config import load_settings
from byo.ops.dashboard import make_server
from byo.runtime.session import DEFAULT_PERSONA
from byo.tools import build_registry
from byo.weather.client import ServiceUnavailable


def weather_registry(settings, conn, geocode="geocode-shanghai", forecast="forecast-metric"):
    client = FakeClient(
        load_fixture(geocode) if geocode else None,
        load_fixture(forecast) if forecast else None,
    )
    return build_registry(conn, settings, weather_client=client, weather_clock=FakeClock()), client


def run(settings, conn, args, **kwargs):
    registry, client = weather_registry(settings, conn, **kwargs)
    return registry.execute("query_weather", args), client


def tool_schema(settings, conn):
    registry, _ = weather_registry(settings, conn)
    return next(item for item in registry.schemas() if item["name"] == "query_weather")


def test_query_weather_is_in_the_registry_with_a_clear_contract(settings, conn):
    registry, _ = weather_registry(settings, conn)
    assert "query_weather" in registry.names()
    schema = tool_schema(settings, conn)
    assert "current weather" in schema["description"]
    assert schema["input_schema"]["required"] == ["place"]
    properties = schema["input_schema"]["properties"]
    assert properties["units"]["enum"] == ["metric", "imperial"]
    assert set(properties) == {"place", "start", "end", "units"}


def test_current_weather_text_states_place_units_and_time(settings, conn):
    output, _ = run(settings, conn, {"place": "Shanghai"})
    assert output.startswith(
        "Weather for Shanghai, Shanghai Municipality, China (Asia/Shanghai)"
    )
    assert "read 2026-11-19 14:30 local." in output
    assert (
        "Now: 10.9 °C (feels 6.8 °C), clear sky, humidity 39%, "
        "wind 10.4 km/h from NW, precipitation 0.0 mm."
    ) in output
    assert output.rstrip().endswith("Weather data by Open-Meteo.com")


def test_the_default_range_has_four_daily_lines(settings, conn):
    output, _ = run(settings, conn, {"place": "Shanghai"})
    daily = [line for line in output.splitlines() if line[:4].isdigit() and line[4] == "-"]
    assert [line.split(":")[0] for line in daily] == [
        "2026-11-19",
        "2026-11-20",
        "2026-11-21",
        "2026-11-22",
    ]
    assert "2026-11-20: mainly clear, 4.2–10.6 °C, rain chance 0%, 0.0 mm" in output


def test_a_single_day_and_a_range_render_one_line_per_day(settings, conn):
    single, _ = run(settings, conn, {"place": "Shanghai", "start": "2026-11-21"})
    assert "2026-11-21: clear sky, 4.3–12.8 °C" in single
    assert "2026-11-22:" not in single
    pair, _ = run(settings, conn, {"place": "Shanghai", "start": "2026-11-20", "end": "2026-11-21"})
    assert "2026-11-20:" in pair and "2026-11-21:" in pair
    assert "2026-11-19:" not in pair


def test_an_out_of_range_date_states_the_window(settings, conn):
    output, _ = run(settings, conn, {"place": "Shanghai", "start": "2026-11-30"})
    assert output.startswith("Error: request out of range:")
    assert "today..today+3" in output
    assert "2026-11-19..2026-11-22" in output


def test_an_unknown_place_is_named_back(settings, conn):
    output, _ = run(settings, conn, {"place": "Xyzzy Town"}, geocode="geocode-empty")
    assert output.startswith("Error: place not recognised:")
    assert "no city matched 'Xyzzy Town'" in output


def test_an_ambiguous_place_lists_candidates_and_no_temperature(settings, conn):
    output, _ = run(settings, conn, {"place": "Springfield"}, geocode="geocode-springfield")
    assert output.startswith("Error: place ambiguous:")
    assert "Springfield, Missouri, United States" in output
    assert "Illinois" in output
    assert "Ask which one:" in output
    assert "°C" not in output and "°F" not in output


def test_an_empty_place_uses_the_default_place_setting(settings, conn):
    client = FakeClient(load_fixture("geocode-shanghai"), load_fixture("forecast-metric"))
    configured = load_settings(
        env={"BYO_HOME": str(settings.home), "BYO_WEATHER_DEFAULT_PLACE": "Shanghai"},
        home=settings.home,
    )
    registry = build_registry(
        conn, configured, weather_client=client, weather_clock=FakeClock()
    )
    output = registry.execute("query_weather", {"place": ""})
    assert output.startswith("Weather for Shanghai,")


def test_a_timeout_has_a_retry_hint(settings, conn):
    client = FakeClient(error=ServiceUnavailable("HTTP 429"))
    registry = build_registry(conn, settings, weather_client=client)
    output = registry.execute("query_weather", {"place": "Shanghai"})
    assert output.startswith("Error: service unavailable:")
    assert "Retry in a moment." in output


def test_a_unit_mismatch_is_data_unavailable(settings, conn):
    output, _ = run(settings, conn, {"place": "Shanghai"}, forecast="forecast-unit-mismatch")
    assert output.startswith("Error: data unavailable:")


def test_imperial_units_are_labelled(settings, conn):
    output, _ = run(
        settings,
        conn,
        {"place": "New York", "units": "imperial"},
        geocode="geocode-shanghai",
        forecast="forecast-imperial",
    )
    assert "43.8 °F" in output
    assert "5.4 mph" in output
    assert "0.0 inch" in output
    assert "°C" not in output


def test_a_second_question_in_one_turn_hits_the_cache(settings, conn):
    registry, client = weather_registry(settings, conn)
    first = registry.execute("query_weather", {"place": "Shanghai"})
    second = registry.execute("query_weather", {"place": "Shanghai"})
    assert first == second
    assert len(client.calls) == 2


def test_a_disabled_tool_is_absent(settings, conn):
    disabled = load_settings(
        env={"BYO_HOME": str(settings.home), "BYO_WEATHER_ENABLED": "false"},
        home=settings.home,
    )
    registry = build_registry(conn, disabled)
    assert "query_weather" not in registry.names()
    unknown = registry.execute("query_weather", {"place": "Shanghai"})
    assert unknown.startswith("Error: unknown tool")


def test_the_persona_tells_the_model_about_the_tool():
    assert "query_weather" in DEFAULT_PERSONA


def test_a_scripted_turn_calls_the_tool_and_records_it(settings):
    client = FakeClient(load_fixture("geocode-shanghai"), load_fixture("forecast-metric"))
    agent = Agent(
        settings,
        adapter=script(
            tool_call("query_weather", {"place": "Shanghai"}),
            text("10.9 °C in Shanghai."),
        ),
        memory=None,
        weather_client=client,
        weather_clock=FakeClock(),
    )
    result = agent.respond("weather in Shanghai?")
    assert result.reply == "10.9 °C in Shanghai."
    events = [event for event in agent.trajectory.events if event["type"] == "tool"]
    assert len(events) == 1
    assert events[0]["tool"] == "query_weather"
    assert events[0]["ok"] is True
    assert events[0]["output"].startswith("Weather for Shanghai")
    assert "sk-" not in events[0]["output"]
    agent.close()


def test_a_failed_call_is_recorded_and_the_turn_continues(settings):
    client = FakeClient(error=ServiceUnavailable("timeout"))
    agent = Agent(
        settings,
        adapter=script(
            tool_call("query_weather", {"place": "Shanghai"}),
            text("Weather is unavailable."),
        ),
        memory=None,
        weather_client=client,
    )
    result = agent.respond("weather in Shanghai?")
    assert result.reply == "Weather is unavailable."
    events = [event for event in agent.trajectory.events if event["type"] == "tool"]
    assert events[0]["ok"] is False
    assert events[0]["output"].startswith("Error: service unavailable:")
    kinds = [
        event["type"]
        for event in agent.trajectory.events
        if event["type"] in ("tool_start", "tool")
    ]
    assert kinds == ["tool_start", "tool"]
    agent.close()


def test_the_dashboard_tools_payload_lists_the_card_and_the_call(settings):
    client = FakeClient(load_fixture("geocode-shanghai"), load_fixture("forecast-metric"))
    agent = Agent(
        settings,
        adapter=script(tool_call("query_weather", {"place": "Shanghai"}), text("Done.")),
        memory=None,
        weather_client=client,
        weather_clock=FakeClock(),
    )
    agent.respond("weather in Shanghai?")
    server = make_server(settings, agent=agent, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/tools") as response:
            payload = json.loads(response.read())
    finally:
        server.shutdown()
        server.server_close()
        agent.close()
    names = [tool["name"] for tool in payload["tools"]]
    assert "query_weather" in names
    results = [row for row in payload["results"] if row["tool"] == "query_weather"]
    assert results and results[0]["ok"] is True
    assert results[0]["output"].startswith("Weather for Shanghai")


def test_an_unknown_units_argument_is_an_argument_error(settings, conn):
    output, _ = run(settings, conn, {"place": "Shanghai", "units": "kelvin"})
    assert output == "Error: argument error: units must be 'metric' or 'imperial', got 'kelvin'"
