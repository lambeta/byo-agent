# byo brand assets

The byo logo: the word "byo" set in **Zilla Slab Bold** (Typotheque, for the Mozilla
Foundation, 2017), outlined to SVG paths and carried on the dashboard theme's signature
sticker — a yellow plate with an ink contour, a hard offset shadow, and a slight −2° tilt.
The plate tilts; the letters stay upright, exactly like the header sticker this logo replaced.

## Why Zilla Slab

The dashboard's display font is Archivo Black, a heavy geometric grotesque; the brief asked
for a logo with a *different* font. Zilla Slab is a slab serif — a different genre, so the
wordmark is visibly its own thing — and its square, bracketed serifs rhyme with the theme's
hard contours and offset shadows. It reads "engineered and printed", which is the product:
built, not configured; readable in an afternoon. Licensed **SIL Open Font License 1.1**
(see OFL.txt in this directory); OFL permits bundling and conversion to outlines.

## Layout of this directory

| File | What it is |
|------|------------|
| ZillaSlab-Bold.ttf | the authoring font. **Not served, not packaged, never loaded at runtime.** |
| OFL.txt | the font's licence, kept beside the font as OFL requires |
| build_logo.py | the generator: glyph outlines → all four artefacts below |
| master-wordmark.svg | the readable master; geometry lives in build_logo.py, not here |
| inline-wordmark.svg | reference for the header copy: same geometry, paints via --byo-* tokens |

Served, derived artefacts live in byo/ops/static/brand/:

| File | Used by |
|------|---------|
| wordmark.svg | README header (self-contained sticker, works on any background) |
| mark.svg | favicon and the collapsed rail — the sticker squared, carrying the initial "b" |

The dashboard header (byo/ops/static/index.html) inlines the wordmark as SVG paths painted
with var(--byo-accent-brand) (plate), var(--byo-ink-on-accent) (letters and contour — they
stay dark on the yellow plate in both schemes) and var(--byo-ink) (shadow — flips with the
theme like every other shadow on the page). That is why the header copy is inline rather than
an img: only inline markup can see the page's tokens under the manual data-theme switch.

## Regenerating

    uv pip install fonttools          # authoring-time only; nothing ships to runtime
    .venv/bin/python brand/build_logo.py

This rewrites the master, both served variants and the inline reference deterministically —
change a colour or padding in build_logo.py, re-run, and every surface follows. After
regenerating, re-embed inline-wordmark.svg into byo/ops/static/index.html (replace the
svg.brand-wordmark element, keep its class/role/aria-label attributes) and run
`make eval`: evals/deterministic/test_brand_assets.py enforces the whole contract
(structure, theming, favicon/rail wiring, serving, this documentation).

## Rejected alternatives

- **Runtime @font-face + live text** — a font swap flashes, shifts layout, and a failed load
  falls back to exactly the fonts the logo must differ from; it would also put a binary in the
  served tree, breaking the offline-asset test. Outlined paths are deterministic bytes.
- **img for the header** — an external SVG cannot see the page's --byo-* tokens or the
  manual data-theme attribute, so dark mode would need swapped files and still flash.
- **Bungee** (display face) — strong sticker vibe but signage-gimmicky, poor at small sizes.
- **Space Mono** — monospace collides with the dashboard's mono data labels; the wordmark would
  read as a label, not a brand.
- **Bricolage Grotesque** — characterful but still a grotesque, too close to Archivo Black to
  count as a font change.
- **Hand-drawn letterforms** — the brief asked for a font, and real type beats amateur lettering.
- **Serving sources from byo/ops/static/** — the font binary would be served and packaged;
  sources stay at repo root, only text SVGs are served.
