"""The Overview shell and its static assets stay dependency-free."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "byo" / "ops" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_overview_is_first_and_loads_map_before_main():
    shell = read("index.html")
    assert shell.index('data-view="overview"') < shell.index('data-view="memory"')
    assert 'id="dock"' in shell and 'id="nav"' in shell  # rail | main | dock shell
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


def test_live_player_is_a_cue_sequencer():
    live = read("js/live.js")
    symbols = (
        "/api/live",
        "MapLive",
        "reconnecting",
        "caught up",
        "mapApplyCueEdges",
        "MAP_LIVE_DWELL",
        "applyCue",
    )
    for symbol in symbols:
        assert symbol in live, symbol
    assert "method: 'POST'" not in live
    assert "fetch('/api/live" in live
    # No global cadence constant: the only pacing is the 150 ms dwell and the 1 s lag bound.
    assert "550" not in live
    assert "650" not in live


def test_the_map_exposes_the_cue_and_note_hooks():
    script = read("js/map.js")
    for symbol in ("mapApplyCueEdges", "mapNote", 'id="map-note"'):
        assert symbol in script, symbol

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


def test_the_live_chat_separates_thinking_tools_and_output():
    script = read("js/main.js")
    render = read("js/render.js")
    live = read("js/live.js")
    for symbol in (
        "round.type = 'thinking'",
        "'Tool call · '",
        "round.type = 'output'",
        "settleRound",
        "closeLive",
    ):
        assert symbol in script, symbol
    assert "data-node=" in render and "lane-" in render
    assert "liveCard" in render and "liveLane" in render
    for symbol in ("litNodes", "byo:lit", "broadcast"):
        assert symbol in live, symbol
    assert "byo:lit" in script and "paintLit" in script


def test_replies_are_markdown_but_user_text_is_not():
    render = read("js/render.js")
    main = read("js/main.js")
    css = read("style.css")
    assert "function renderMarkdown(" in render
    assert "const text = esc(String(source" in render
    assert "https?:|mailto:" in render
    assert "javascript:" not in render
    assert "renderMarkdown(message.content)" in main
    assert "esc(message.content)" in main
    assert ".md pre" in css and ".md code" in css and ".bubble-body.md" in css
    # Tables, images, nested lists and task lists are part of the subset.
    assert "function mdTable(" in render and "function mdList(" in render
    assert "md-table" in render and "<img src=" in render and 'class="task"' in render
    assert ".md table" in css and ".md img" in css and ".md li.task" in css


def test_the_composer_fits_its_wrapped_placeholder():
    css = read("style.css")
    main = read("js/main.js")
    input_block = css[css.index("#chat-input {"):]
    input_block = input_block[: input_block.index("}")]
    assert "min-height: calc(2.8em + 22px)" in input_block
    chatbar = css[css.index(".chatbar {"):]
    chatbar = chatbar[: chatbar.index("}")]
    assert "flex: none" in chatbar
    assert "input.style.height = ''" in main


def test_the_chat_log_reads_oldest_first():
    shell = read("index.html")
    log = shell[shell.index('id="docklog"'):]
    assert log.index('id="chat-history"') < log.index('id="chat-live"'), (
        "the transcript must come before the live card so the newest turn is at the bottom"
    )
