# Quickstart: byo Logo & Wordmark

End-to-end validation that the feature shipped. Prerequisites: `uv venv && uv pip install -e ".[dev]"`.
Everything here is offline; the dashboard steps need a `BYO_API_KEY` only because the server boots
an agent — the asset tests need nothing.

## 1. Deterministic gate (offline, no key)

```bash
make eval        # includes evals/deterministic/test_brand_assets.py
make gate        # one-line summary; non-zero on failure
```

**Expected**: all green. The new tests prove: served SVGs are self-contained outlined-path files;
the header carries an accessible, theme-token-driven inline SVG; favicon + collapsed-rail wiring
exists; no `brand-sticker` remnant; licence + design note present; README references the wordmark.

## 2. Dashboard — first impression (US1)

```bash
uv run byo dashboard   # http://127.0.0.1:7777
```

1. Open the dashboard → the sidebar header shows the new "byo" wordmark on the yellow sticker.
   **Expected**: instantly readable as "byo"; visibly *not* the old Archivo Black letters; sticker,
   contour and hard shadow match the surrounding theme.
2. Resize the window narrow → **Expected**: no overflow, no wrap, no layout shift of the rail.
3. Collapse the rail (chevron) → **Expected**: the compact mark (yellow square sticker with "b")
   remains at the top of the rail.

## 3. Theme robustness (US2)

1. Click `theme: light` in the rail footer to switch to dark → **Expected**: the inline wordmark
   repaints (ink and shadow follow the dark tokens), contrast holds, no flash of unstyled logo.
2. Switch back to light → same check.
3. Look at the browser tab → **Expected**: the compact mark favicon, recognisable at tab size.
4. Squint test: header wordmark at normal size, favicon at 16 px → **Expected**: both read as the
   same brand.

## 4. README surface (US2)

Open `README.md` in a markdown preview (or push to a branch and view on GitHub).
**Expected**: the header shows `wordmark.svg` — the same sticker wordmark as the dashboard —
rendered on both light and dark GitHub themes.

## 5. Source maintainability (US3)

1. Read `brand/README.md` → **Expected**: you can state the typeface, why it was chosen, and how
   to regenerate the variants without asking anyone.
2. Open `brand/master-wordmark.svg` in a text editor → **Expected**: readable, commented XML.
3. Confirm `brand/OFL.txt` sits next to `brand/zilla-slab-bold.woff2`.

## Failure signals

- Header shows plain text or old sticker → integration (contract §3) broken.
- Logo disappears in dark mode → inline SVG hard-codes colours (contract §3.2 violated).
- `make eval` fails on `test_style_offline.py` → a binary or external URL leaked into
  `byo/ops/static/` (the font must stay in repo-root `brand/`).
- Favicon missing → check `<link rel="icon">` and `GET /static/brand/mark.svg` status/type.
