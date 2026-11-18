"""No static asset reaches the network: no imports, no remote URLs, no CDN."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "byo" / "ops" / "static"


def _assets():
    return sorted(p for p in STATIC.rglob("*") if p.is_file())


def test_static_tree_is_not_empty():
    names = [p.name for p in _assets()]
    assert "index.html" in names and "style.css" in names
    assert any(p.suffix == ".js" for p in _assets())


def test_no_external_request_in_any_static_asset():
    for path in _assets():
        text = path.read_text(encoding="utf-8")
        name = str(path.relative_to(STATIC))
        assert "@import" not in text, name
        assert "https://" not in text, name
        assert "http://" not in text.replace("http://www.w3.org", ""), name
        assert "cdn." not in text, name
        for url in re.findall(r"url\(([^)]*)\)", text):
            assert "http" not in url and "//" not in url, (name, url)
