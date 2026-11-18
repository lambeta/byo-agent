# Contracts: Brand Assets

The external interface of this feature is a set of files with structural guarantees. Tests in
`evals/deterministic/test_brand_assets.py` assert every clause below; the manual visual layer is in
[quickstart.md](../quickstart.md).

## 1. Asset inventory

| Path | Kind | Purpose |
|------|------|---------|
| `brand/master-wordmark.svg` | source | editable master (comments/guides allowed) |
| `brand/ZillaSlab-Bold.ttf` | source | authoring font (never served, never loaded at runtime) |
| `brand/OFL.txt` | source | SIL OFL 1.1 licence text |
| `brand/README.md` | doc | design note: mechanism, typeface, regeneration steps, rejected alternatives |
| `byo/ops/static/brand/wordmark.svg` | served | full wordmark, self-contained sticker |
| `byo/ops/static/brand/mark.svg` | served | compact square mark ("b" monogram on sticker) |

## 2. SVG structural contract (served variants)

For each file in `byo/ops/static/brand/*.svg`:

1. Well-formed XML, single `<svg>` root, explicit `viewBox`; `width`/`height` omitted or
   proportional to the viewBox (scaling is the consumer's job).
2. Contains `<path>` letterform data; MUST NOT contain `<text>`, `<image>`, `<script>`,
   `<foreignObject>`, `@font-face`, or any `http(s)://` reference other than the SVG
   namespace declaration (`http://www.w3.org/2000/svg`).
3. Colour literal set ⊆ { brand yellow `#ffd02f`, ink `#1a1a1a`, ink-on-accent `#1a1a1a`,
   white `#ffffff` } — the sticker is scheme-independent by construction.
4. `mark.svg` is square (equal viewBox sides) and legible at 16 px: one letter, no fine detail
   below ~1/16 of the viewBox.
5. Total size per file < 10 KB uncompressed.

## 3. Header integration contract (`byo/ops/static/index.html`, `style.css`)

1. The `.brand` slot contains an **inline** `<svg>` with `role="img"` and `aria-label="byo"`
   (accessible name preserved; the visible wordmark is paths, so the label carries the name).
2. Inline SVG paints via `currentColor` / `var(--byo-*)` references only — no hard-coded hex in
   the inline copy — so it repaints with `[data-theme="dark"]` (FR-005).
3. Favicon declared as `<link rel="icon" type="image/svg+xml" href="/static/brand/mark.svg">`.
4. Collapsed rail shows the compact mark (an `<img>` of `mark.svg` or a second inline copy);
   `body.rail-collapsed .brand` no longer hides the brand.
5. No `brand-sticker` class or rule remains; the rail's layout, keyboard order, and collapse
   behaviour are otherwise unchanged (no reflow: header keeps its current box dimensions).

## 4. Serving contract (`byo/ops/dashboard.py`)

1. `GET /static/brand/wordmark.svg` and `GET /static/brand/mark.svg` return 200 with
   `Content-Type: image/svg+xml` (the existing `CONTENT_TYPES` table already covers `.svg`;
   the contract pins the behaviour).
2. No route, API, or SSE change.

## 5. Source & licence contract

1. `brand/OFL.txt` exists and names the SIL Open Font License, Version 1.1.
2. `brand/README.md` states: the typeface (Zilla Slab Bold), how variants derive from
   `master-wordmark.svg`, and the rejected alternatives (runtime webfont, `<img>` header,
   single-zone assets).
3. `README.md` (repo root) references `byo/ops/static/brand/wordmark.svg` in its header.

## 6. Test mapping

| Contract clause | Test (evals/deterministic/test_brand_assets.py) |
|-----------------|--------------------------------------------------|
| §2.1–2.3, 2.5 | `test_served_svgs_are_self_contained` |
| §2.4 | `test_mark_is_square_and_simple` |
| §3.1–3.2 | `test_header_inline_svg_accessible_and_themed` |
| §3.3–3.5 | `test_favicon_and_rail_and_no_sticker_remnants` |
| §4 | `test_brand_assets_served` (extends existing dashboard test patterns) |
| §5 | `test_licence_and_design_note_present`, `test_readme_references_wordmark` |
