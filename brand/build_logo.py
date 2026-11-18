#!/usr/bin/env python3
"""Regenerate every byo logo asset from brand/ZillaSlab-Bold.ttf.

Mechanism: extract the glyph outlines of the wordmark letters with fontTools,
compose them on one baseline with fixed tracking, and wrap them in the theme's
sticker — a yellow plate with an ink contour, a hard offset shadow and the
signature slight tilt (the plate tilts, the letters stay upright, exactly like
the header sticker this logo replaces). The same builder emits four artefacts:

  brand/master-wordmark.svg          editable master (comments, font-unit grid)
  byo/ops/static/brand/wordmark.svg  served full wordmark, self-contained
  byo/ops/static/brand/mark.svg      served compact square mark ("b")
  brand/inline-wordmark.svg          reference for the header: identical
                                     geometry, paints via --byo-* tokens so it
                                     repaints with [data-theme="dark"]

Colours are the theme tokens baked to literals in the served files:
  yellow #ffd02f = --byo-accent-brand, ink #1a1a1a = --byo-ink / --byo-ink-on-accent.

Run:  .venv/bin/python brand/build_logo.py
Needs: fonttools (authoring-time only; nothing here ships to runtime code).

Rejected alternatives: runtime @font-face + live text (font swap / CLS / a
failed load falls back to the fonts this logo must differ from); hand-drawn
letterforms (the brief asked for a font change, and real type beats amateur
lettering); a build pipeline (one stdlib+fonttools script is enough).
"""

from __future__ import annotations

import math
from pathlib import Path

import re

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

NUM = re.compile(r"-?\d+\.\d+")


def round_path(d: str, digits: int = 1) -> str:
    """Round every float in a path d-string; keeps files small and diffable."""
    return NUM.sub(lambda m: rounded(float(m.group(0))), d)

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
FONT = ROOT / "ZillaSlab-Bold.ttf"

YELLOW = "#ffd02f"  # --byo-accent-brand
INK = "#1a1a1a"  # --byo-ink / --byo-ink-on-accent

# Wordmark composition, in font units (Zilla Slab upem = 1000).
LETTERS = "byo"
TRACKING = 60  # 0.06em — echoes the theme's tracked labels, keeps "byo" one word
PAD_LEFT = 250
PAD_RIGHT = 250
PAD_TOP = 180
PAD_BOTTOM = 210  # a touch more: balances the y descender optically
TILT_DEG = -2.0  # screen-space tilt of the sticker plate
DISPLAY_HEIGHT_PX = 30.0  # header render height; px geometry derives from this
CONTOUR_PX = 2.0  # --byo-contour-w
SHADOW_PX = 4.0  # --byo-shadow-rest: 4px 4px 0
RADIUS_PX = 3.0  # --byo-radius

# Compact mark geometry (own square canvas, same upem grid).
MARK_CANVAS = 1000
MARK_INSET = 120  # sticker inset from canvas edge
MARK_SHADOW = 90
MARK_CONTOUR = 60
MARK_RADIUS = 90
MARK_GLYPH_FILL = 0.60  # glyph height as a fraction of the sticker's inner height


def load_letters(font: TTFont, letters: str):
    """Path data, advance and bounds per letter, in font units (y-up)."""
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    out = []
    for ch in letters:
        name = cmap[ord(ch)]
        pen = SVGPathPen(glyph_set)
        glyph_set[name].draw(pen)
        bounds_pen = BoundsPen(glyph_set)
        glyph_set[name].draw(bounds_pen)
        advance = font["hmtx"][name][0]
        out.append(
            {
                "ch": ch,
                "d": round_path(pen.getCommands()),
                "advance": advance,
                "bounds": bounds_pen.bounds,  # (xMin, yMin, xMax, yMax), y-up
            }
        )
    return out


def rounded(value: float) -> str:
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text if text not in ("-0", "") else "0"


def rotated_bbox(x: float, y: float, w: float, h: float, deg: float, cx: float, cy: float):
    """Screen-space bbox of a rect rotated by deg around (cx, cy)."""
    rad = math.radians(deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    xs, ys = [], []
    for px, py in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
        dx, dy = px - cx, py - cy
        xs.append(cx + dx * cos_a - dy * sin_a)
        ys.append(cy + dx * sin_a + dy * cos_a)
    return min(xs), min(ys), max(xs), max(ys)


def wordmark_geometry(letters):
    """Compose letters and derive the sticker/viewBox geometry (screen coords)."""
    # Compose on a baseline: letters drawn y-up, flipped per-path; the baseline
    # sits at BASE in screen space (y-down).
    y_min = min(g["bounds"][1] for g in letters)  # lowest point (y descender)
    y_max = max(g["bounds"][3] for g in letters)  # highest point (b ascender)
    total_w = sum(g["advance"] for g in letters) + TRACKING * (len(letters) - 1)
    letters_h = y_max - y_min

    sticker_h = letters_h + PAD_TOP + PAD_BOTTOM
    sticker_w = total_w + PAD_LEFT + PAD_RIGHT
    scale = DISPLAY_HEIGHT_PX / sticker_h
    contour = CONTOUR_PX / scale
    shadow = SHADOW_PX / scale
    radius = RADIUS_PX / scale

    base = PAD_TOP + y_max  # screen y of the baseline inside the sticker
    sticker_x, sticker_y = -PAD_LEFT, base - y_max - PAD_TOP
    cx, cy = sticker_x + sticker_w / 2, sticker_y + sticker_h / 2

    # viewBox: rotated (sticker ∪ shadow) corners, union the upright letters.
    shadow_box = (
        sticker_x + shadow,
        sticker_y + shadow,
        sticker_w,
        sticker_h,
    )
    bx0, by0, bx1, by1 = rotated_bbox(*shadow_box, TILT_DEG, cx, cy)
    sx0, sy0, sx1, sy1 = rotated_bbox(sticker_x, sticker_y, sticker_w, sticker_h, TILT_DEG, cx, cy)
    vx0 = min(bx0, sx0, 0)
    vy0 = min(by0, sy0, base - y_max)
    vx1 = max(bx1, sx1, total_w)
    vy1 = max(by1, sy1, base - y_min)
    margin = contour
    view_box = (vx0 - margin, vy0 - margin, vx1 - vx0 + 2 * margin, vy1 - vy0 + 2 * margin)

    return {
        "letters": letters,
        "base": base,
        "total_w": total_w,
        "sticker": (sticker_x, sticker_y, sticker_w, sticker_h),
        "center": (cx, cy),
        "contour": contour,
        "shadow": shadow,
        "radius": radius,
        "view_box": view_box,
        "scale": scale,
    }


def letter_paths(geom, fill: str) -> str:
    parts = [f'<g fill="{fill}">']
    x = 0.0
    for glyph in geom["letters"]:
        # flip y: font units are y-up, SVG is y-down
        parts.append(
            f'  <path transform="translate({rounded(x)} {rounded(geom["base"])}) '
            f'scale(1 -1)" d="{glyph["d"]}"/> <!-- {glyph["ch"]} -->'
        )
        x += glyph["advance"] + TRACKING
    parts.append("</g>")
    return "\n".join(parts)


def sticker_group(geom, yellow: str, figure: str, shadow: str) -> str:
    sx, sy, sw, sh = geom["sticker"]
    cx, cy = geom["center"]
    shadow_off = geom["shadow"]
    contour = geom["contour"]
    radius = geom["radius"]
    return (
        f'<g transform="rotate({TILT_DEG} {rounded(cx)} {rounded(cy)})">\n'
        f'  <!-- hard offset shadow: theme token byo-shadow-rest, zero blur -->\n'
        f'  <rect x="{rounded(sx + shadow_off)}" y="{rounded(sy + shadow_off)}" '
        f'width="{rounded(sw)}" height="{rounded(sh)}" rx="{rounded(radius)}" fill="{shadow}"/>\n'
        f'  <!-- the sticker plate -->\n'
        f'  <rect x="{rounded(sx)}" y="{rounded(sy)}" width="{rounded(sw)}" '
        f'height="{rounded(sh)}" rx="{rounded(radius)}" fill="{yellow}" '
        f'stroke="{figure}" stroke-width="{rounded(contour)}"/>\n'
        f"</g>"
    )


def wordmark_svg(geom, yellow: str, figure: str, shadow: str, note: str) -> str:
    vx, vy, vw, vh = (rounded(v) for v in geom["view_box"])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vx} {vy} {vw} {vh}">
  <!-- {note} -->
  <!-- letters: Zilla Slab Bold outlines (SIL OFL 1.1), composed on one baseline; -->
  <!-- the sticker plate tilts {TILT_DEG}deg, the letters stay upright. -->
  {sticker_group(geom, yellow, figure, shadow)}
  {letter_paths(geom, figure)}
</svg>
"""


def mark_svg(font: TTFont) -> str:
    glyph_set = font.getGlyphSet()
    name = font.getBestCmap()[ord("b")]
    pen = SVGPathPen(glyph_set)
    glyph_set[name].draw(pen)
    bounds_pen = BoundsPen(glyph_set)
    glyph_set[name].draw(bounds_pen)
    x_min, y_min, x_max, y_max = bounds_pen.bounds

    half = MARK_CANVAS / 2
    sticker_x = MARK_INSET
    sticker_y = MARK_INSET
    sticker_s = MARK_CANVAS - 2 * MARK_INSET
    cx = cy = half

    inner = sticker_s - 2 * MARK_CONTOUR
    target_h = inner * MARK_GLYPH_FILL
    glyph_h = y_max - y_min
    scale = target_h / glyph_h
    # centre the glyph bbox on the sticker centre (screen coords, y-down)
    glyph_w = (x_max - x_min) * scale
    draw_h = glyph_h * scale
    tx = half - glyph_w / 2 - x_min * scale
    ty = half + draw_h / 2 - y_max * scale  # flip: top of glyph first

    # viewBox: rotated sticker + shadow, padded
    bx0, by0, bx1, by1 = rotated_bbox(
        sticker_x + MARK_SHADOW, sticker_y + MARK_SHADOW, sticker_s, sticker_s, TILT_DEG, cx, cy
    )
    sx0, sy0, sx1, sy1 = rotated_bbox(sticker_x, sticker_y, sticker_s, sticker_s, TILT_DEG, cx, cy)
    vx0, vy0 = min(bx0, sx0) - 10, min(by0, sy0) - 10
    vw, vh = max(bx1, sx1) - vx0 + 10, max(by1, sy1) - vy0 + 10
    side = max(vw, vh)  # keep the mark square
    vx0 -= (side - vw) / 2
    vy0 -= (side - vh) / 2

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{rounded(vx0)} {rounded(vy0)} {rounded(side)} {rounded(side)}">
  <!-- byo compact mark: the wordmark's sticker squared, carrying its initial. -->
  <!-- "b" in Zilla Slab Bold (SIL OFL 1.1), outlined; legible at 16px. -->
  <g transform="rotate({TILT_DEG} {rounded(cx)} {rounded(cy)})">
    <rect x="{rounded(sticker_x + MARK_SHADOW)}" y="{rounded(sticker_y + MARK_SHADOW)}" width="{sticker_s}" height="{sticker_s}" rx="{MARK_RADIUS}" fill="{INK}"/>
    <rect x="{sticker_x}" y="{sticker_y}" width="{sticker_s}" height="{sticker_s}" rx="{MARK_RADIUS}" fill="{YELLOW}" stroke="{INK}" stroke-width="{MARK_CONTOUR}"/>
  </g>
  <path transform="translate({rounded(tx)} {rounded(ty)}) scale({rounded(scale)} {rounded(-scale)})" fill="{INK}" d="{round_path(pen.getCommands())}"/>
</svg>
"""


def main() -> None:
    font = TTFont(FONT)
    letters = load_letters(font, LETTERS)
    geom = wordmark_geometry(letters)

    master = wordmark_svg(
        geom,
        YELLOW,
        INK,
        INK,
        "byo master wordmark — edit geometry in brand/build_logo.py, not here.",
    )
    (ROOT / "master-wordmark.svg").write_text(master, encoding="utf-8")

    served = wordmark_svg(
        geom,
        YELLOW,
        INK,
        INK,
        "byo wordmark — self-contained sticker; regenerable via brand/build_logo.py.",
    )
    (REPO / "byo" / "ops" / "static" / "brand" / "wordmark.svg").write_text(served, encoding="utf-8")

    inline_note = (
        "byo wordmark, header inline form — paints follow the page's byo-* tokens: "
        "sticker = byo-accent-brand; letters/contour = byo-ink-on-accent (stays dark "
        "on the yellow plate in both schemes); shadow = byo-ink (flips with the theme, "
        "like every other shadow on the page)."
    )
    inline = wordmark_svg(
        geom,
        "var(--byo-accent-brand)",
        "var(--byo-ink-on-accent)",
        "var(--byo-ink)",
        inline_note,
    )
    (ROOT / "inline-wordmark.svg").write_text(inline, encoding="utf-8")

    (REPO / "byo" / "ops" / "static" / "brand" / "mark.svg").write_text(mark_svg(font), encoding="utf-8")

    vw = geom["view_box"][2] * geom["scale"]
    vh = geom["view_box"][3] * geom["scale"]
    print(f"wordmark: viewBox {rounded(geom['view_box'][2])} x {rounded(geom['view_box'][3])} units")
    print(f"          renders {vw:.1f} x {vh:.1f} px at height {DISPLAY_HEIGHT_PX}px")
    print("wrote: brand/master-wordmark.svg, brand/inline-wordmark.svg,")
    print("       byo/ops/static/brand/wordmark.svg, byo/ops/static/brand/mark.svg")


if __name__ == "__main__":
    main()
