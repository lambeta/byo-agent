"""The Overview shell and its static assets stay dependency-free."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "byo" / "ops" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_overview_is_first_and_loads_map_before_main():
    shell = read("index.html")
    assert shell.index('data-view="overview"') < shell.index('data-view="chat"')
    for script in ("api.js", "render.js", "map.js", "live.js", "observe.js", "dock.js", "main.js"):
        assert "/static/js/" + script in shell, script
    assert shell.index("map.js") < shell.index("live.js") < shell.index("main.js")
    assert shell.rindex("main.js") > shell.rindex("live.js")


def test_map_assets_have_no_external_or_build_dependency():
    for name in ("js/map.js", "js/live.js", "style.css", "index.html"):
        text = read(name)
        assert "http://" not in text.replace("http://www.w3.org", ""), name
        assert "https://" not in text, name
        assert "cdn." not in text, name
        assert "import " not in text, name


def test_map_script_has_the_contract_hooks():
    script = read("js/map.js")
    for symbol in (
        "overviewView", "mapBind", "mapNodeClick", "mapSetWindow",
        "renderTurnDetail", "mapCloseDetail", "data-stage", "data-state",
    ):
        assert symbol in script, symbol
    assert "map-status" in script and "Text view of the map" in script
    assert "role=\"status\"" in script


def test_turn_card_and_map_share_the_stage_vocabulary():
    render = read("js/render.js")
    script = read("js/map.js")
    for stage in ("gate", "loop", "tool", "reply"):
        assert 'data-stage="' + stage + '"' in render, stage
        assert "data-stage" in script
    assert 'data-state="' in render
    states = (
        "idle", "live", "done", "skipped", "degraded", "failed", "not-reached", "partial"
    )
    for state in states:
        assert state in script, state


def test_reduced_motion_and_text_view_are_present():
    css = read("style.css")
    assert "prefers-reduced-motion" in css
    assert ".map-text" in css
    assert ".turn-detail" in css


def test_live_player_is_read_only_and_cursor_driven():
    live = read("js/live.js")
    symbols = ("/api/events?cursor=", "MapLive", "reconnecting", "caught up", "mapMarkUnreached")
    for symbol in symbols:
        assert symbol in live, symbol
    assert "method: 'POST'" not in live
    assert "fetch('/api/events" in live

def test_shell_loads_all_seven_scripts_in_order():
    shell = read("index.html")
    order = ["api.js", "render.js", "map.js", "live.js", "observe.js", "dock.js", "main.js"]
    positions = []
    for script in order:
        marker = "/static/js/" + script
        assert marker in shell, script
        positions.append(shell.index(marker))
    assert positions == sorted(positions), order


def test_static_server_serves_every_script():
    from byo.ops.dashboard import STATIC

    for script in ("api.js", "render.js", "map.js", "live.js", "observe.js", "dock.js", "main.js"):
        assert (STATIC / "js" / script).is_file(), script
    assert (STATIC / "style.css").is_file()
    assert (STATIC / "index.html").is_file()


def test_no_reference_brand_assets_are_copied():
    for name in ("index.html", "style.css", "js/map.js", "js/live.js"):
        text = read(name)
        for word in ("waku", "Waku", "InstrumentSans", "Playfair", "waku-mark"):
            assert word not in text, (name, word)
