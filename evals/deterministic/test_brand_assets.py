"""Brand assets: the byo logo system — structure, integration, offline.

Contract: specs/005-byo-logo-design/contracts/brand-assets.md. Every clause maps
to a test below; all checks are pure filesystem or localhost assertions.
"""

from __future__ import annotations

import re
import threading
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from scripted import script, text

from byo.app import Agent
from byo.ops.dashboard import make_server

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "byo" / "ops" / "static"
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "style.css").read_text(encoding="utf-8")
BRAND_DIR = STATIC / "brand"
SOURCE_DIR = ROOT / "brand"
README = (ROOT / "README.md").read_text(encoding="utf-8")

ALLOWED_HEX = {"#ffd02f", "#1a1a1a", "#ffffff"}


def _brand_svg() -> str:
    """The inline logo <svg> inside the rail's .brand slot."""
    match = re.search(
        r'<span class="brand">.*?(<svg\b[^>]*>.*?</svg>)', INDEX, re.S
    )
    assert match, ".brand slot must contain an inline <svg> logo"
    return match.group(1)


# --- contract §3.1–3.2: header integration ---------------------------------


def test_header_inline_svg_accessible_and_themed():
    svg = _brand_svg()
    tag = svg.split(">", 1)[0]
    assert 'role="img"' in tag, "logo svg needs role=img"
    assert 'aria-label="byo"' in tag, "logo svg needs an accessible name"
    assert re.search(r"\bviewBox=", tag), "logo svg needs an explicit viewBox"
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", svg), (
        "inline logo must paint via var(--byo-*) only, no hard-coded hex"
    )
    assert "var(--byo-accent-brand)" in svg, "sticker fill must follow the brand token"
    assert "var(--byo-ink" in svg, "letters/contour/shadow must follow ink tokens"


# --- contract §3.5: no remnants ----------------------------------------------


def test_no_sticker_remnants():
    assert "brand-sticker" not in INDEX, "old text sticker markup still in index.html"
    assert "brand-sticker" not in CSS, "old text sticker rules still in style.css"


# --- contract §2: served SVG structure ---------------------------------------


def _served(name: str) -> tuple[str, ET.Element]:
    path = BRAND_DIR / name
    assert path.is_file(), f"{name} missing from {BRAND_DIR}"
    assert path.stat().st_size < 10 * 1024, f"{name} must stay under 10 KB"
    text_content = path.read_text(encoding="utf-8")
    root = ET.fromstring(text_content)
    return text_content, root


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


@pytest.mark.parametrize("name", ["wordmark.svg", "mark.svg"])
def test_served_svgs_are_self_contained(name: str):
    text_content, root = _served(name)
    assert _local_name(root) == "svg"
    assert root.get("viewBox"), f"{name} needs an explicit viewBox"
    assert root.get("width") is None and root.get("height") is None, (
        f"{name}: scaling is the consumer's job, no width/height attributes"
    )
    banned = {"text", "image", "script", "foreignObject"}
    seen = {_local_name(el) for el in root.iter()}
    assert not (banned & seen), f"{name} must be path/shape-only, found {banned & seen}"
    without_ns = text_content.replace("http://www.w3.org/2000/svg", "")
    assert "http://" not in without_ns and "https://" not in without_ns, (
        f"{name} must not reference the network"
    )
    hexes = {h.lower() for h in re.findall(r"#[0-9a-fA-F]{3,8}\b", text_content)}
    assert hexes <= ALLOWED_HEX, f"{name} uses colours outside the brand set: {hexes}"


def test_mark_is_square_and_simple():
    _, root = _served("mark.svg")
    box = [float(v) for v in root.get("viewBox").split()]
    assert box[2] == box[3], "compact mark must be square"
    paths = [el for el in root.iter() if _local_name(el) == "path"]
    assert len(paths) == 1, "compact mark carries exactly one letter"


# --- contract §3.3–3.4: favicon + collapsed rail ------------------------------


def test_favicon_and_rail_wiring():
    assert '<link rel="icon" type="image/svg+xml" href="/static/brand/mark.svg">' in INDEX, (
        "favicon link missing from <head>"
    )
    assert re.search(
        r'<img[^>]*class="brand-mark"[^>]*src="/static/brand/mark\.svg"', INDEX
    ), "collapsed-rail compact mark missing from the .brand slot"
    assert re.search(
        r"body\.rail-collapsed \.brand-wordmark\s*\{[^}]*display:\s*none", CSS
    ), "collapsed rail must hide the full wordmark"
    assert re.search(
        r"body\.rail-collapsed \.brand-mark\s*\{[^}]*display:\s*block", CSS
    ), "collapsed rail must show the compact mark"
    assert not re.search(
        r"body\.rail-collapsed \.brand\s*\{[^}]*display:\s*none", CSS
    ), "the brand slot itself must not vanish when the rail collapses"


# --- contract §4: serving -----------------------------------------------------


@pytest.fixture
def brand_server(settings):
    agent = Agent(settings, adapter=script(text("ok")), memory=None)
    srv = make_server(settings, agent=agent, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


@pytest.mark.parametrize("name", ["wordmark.svg", "mark.svg"])
def test_brand_assets_served(brand_server, name: str):
    host, port = brand_server.server_address
    with urllib.request.urlopen(f"http://{host}:{port}/static/brand/{name}") as response:
        assert response.status == 200
        assert response.headers.get_content_type() == "image/svg+xml"
        body = response.read().decode("utf-8")
    assert body.lstrip().startswith("<svg"), name


# --- contract §5: sources, licence, design note -------------------------------


def test_licence_and_design_note_present():
    ofl = (SOURCE_DIR / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE" in ofl and "Version 1.1" in ofl, (
        "the font licence must be recorded next to the font"
    )
    assert (SOURCE_DIR / "ZillaSlab-Bold.ttf").is_file(), "authoring font missing"
    note_path = SOURCE_DIR / "README.md"
    assert note_path.is_file(), "brand design note missing"
    note = note_path.read_text(encoding="utf-8").lower()
    assert "zilla slab" in note, "design note must name the typeface"
    assert "build_logo.py" in note, "design note must document regeneration"
    assert "rejected" in note, "design note must record rejected alternatives"


def test_readme_references_wordmark():
    assert "byo/ops/static/brand/wordmark.svg" in README, (
        "README must show the served wordmark"
    )
