"""Static contracts for the dashboard's views and navigation.

Mechanism: pure source assertions — every view function main.js calls is defined
in a script index.html loads; no view builder carries the bare-return-then-newline
pattern that made the Memory view render "Undefined" (spec 006, RC-1); every map
destination is handled by mapNodeClick and lands on a route main.js renders
(spec 006, RC-2).

Rejected alternative: executing the JS under Node. A second toolchain in the
default test path costs more than these contracts are worth.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "byo" / "ops" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def loaded_scripts() -> list[str]:
    shell = read("index.html")
    return [m.group(1) for m in re.finditer(r'src="/static/js/([a-z]+\.js)"', shell)]


def test_every_view_function_main_calls_is_defined():
    main = read("js/main.js")
    called = set(re.findall(r"\b(\w+View)\(", main))
    assert called, "main.js should call view builders"
    body = "\n".join(read(f"js/{name}") for name in loaded_scripts())
    for name in sorted(called):
        assert re.search(rf"function {name}\b", body), f"{name} is not defined in any loaded script"


def test_no_view_builder_returns_undefined_by_asi():
    """A bare 'return' followed by a newline returns undefined (spec 006, RC-1)."""
    offenders = []
    for name in loaded_scripts():
        text = read(f"js/{name}")
        if re.search(r"\breturn\s*\n\s*['\"<(]", text):
            offenders.append(name)
    assert not offenders, f"bare-return-then-newline in: {offenders}"


def test_every_map_destination_is_handled_and_routed():
    """map.py destinations -> mapNodeClick branches -> views main.js renders."""
    map_py = (ROOT / "byo" / "ops" / "map.py").read_text(encoding="utf-8")
    destinations = set(re.findall(r'"destination":\s*"([a-z]+)"', map_py))
    assert destinations, "map.py should declare node destinations"
    map_js = read("js/map.js")
    for dest in sorted(destinations):
        assert f"destination === '{dest}'" in map_js, f"mapNodeClick does not handle '{dest}'"
    navigates = {"memory": "memory", "observability": "observe", "tools": "tools"}
    main = read("js/main.js")
    heads = set(re.findall(r"^  (\w+): \[", main, flags=re.M))
    for dest, view in navigates.items():
        if dest in destinations:
            assert view in heads, f"main.js VIEW_HEADS has no '{view}' for destination '{dest}'"


def test_nav_has_a_link_for_every_routed_view():
    shell = read("index.html")
    main = read("js/main.js")
    heads = set(re.findall(r"^  (\w+): \[", main, flags=re.M))
    linked = set(re.findall(r'data-view="(\w+)"', shell))
    for view in sorted(heads):
        assert view in linked, f'no nav link data-view="{view}"'
