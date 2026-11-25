# 2D graphics (`tools/graphics/`)

One package draws every 2D graphic in the pipeline: stat cards, tallies, plans, boards, labels, archive mats. Tokens live in `workflow/style.json` under `graphics`; nothing else holds a colour, a size or a margin.

```python
from tools.graphics import get, PRIMITIVES, get_preset
from tools.graphics.encode import stream_to_mp4, render_to_file

frames = get("tally").render(spec, seconds=3, canvas=(1920, 1080), fps=30)   # a generator
stream_to_mp4(frames, "tally.mov", fps=30, alpha=True)
render_to_file("ratio-1846", {}, 4.0, "ratio.mp4")                           # a preset by name
```

## The contract

Every primitive (a `Primitive` object in `PRIMITIVES`, which is what a module per name would expose) has:

| member | meaning |
|---|---|
| `render(spec, seconds, canvas=(1920,1080), fps=30, tokens=None)` | validates immediately, then returns a **generator** of exactly `round(seconds*fps)` RGBA frames; frame *i* is `frame_at(spec, i/fps)` |
| `frame_at(spec, t, canvas, tokens)` | one RGBA frame at local time `t` |
| `SCHEMA` | JSON-schema-like dict, checked by `spec.validate`; unknown fields are refused |
| `OVERLAY` | `True` for transparent overlays (encode as ProRes 4444 `.mov`), `False` for opaque full frames (H.264 `.mp4`) |

Rules:

* **Never a list of frames.** Static layers (background, mat, unchanging cards) are drawn once per `render` call and `.copy()`d into each frame. Why: 600 frames of 1920x1080 RGBA is 8.3 MB each, about 5 GB if held. `stream_to_mp4` pulls one frame at a time.
* Times in a spec are **local seconds from 0**. A build is `{"at": s, "dur": s}` or `[at, dur]`. A discrete element is invisible one frame before `at` and visible on the frame that reaches `at` (`Ctx.appear` starts at 30% strength, never at zero).
* Deterministic: the same spec gives identical bytes.
* **Type** is a fraction of frame height. `label` and `number` may never be set below `mobile_floor` (0.06 and 0.10): `Ctx` raises `ValueError`, including for a spec's own `type` override. `caption` (0.045, matches `archive.source_card`) is for provenance tags only (credit, source).
* **Safe margin** 0.05 of width on the sides and of height top and bottom. Every drawn pixel stays inside it; full-frame backgrounds are the exception. `split` dividers also run edge to edge, because they separate video panes.
* Text sits on a plate whose colour is chosen for contrast (`Ctx.text_on`); all token pairs in use reach WCAG 4.5:1.
* Bad specs raise `ValueError` with the path and the problem (`tally.left.marks: -1 is below the minimum 0`).

## Tokens (`workflow/style.json` -> `graphics`)

```
palette: ink paper accent warm cool data_a data_b danger mat   (hex strings)
type: display 0.20, number 0.10, label 0.06, caption 0.045     (x frame height)
mobile_floor: label 0.06, number 0.10
stroke_fraction 0.004, corner_radius_fraction 0.012, safe_margin_fraction 0.05
motion: ease_in cubic_in, ease_out cubic_out, settle back_out
build_stagger_seconds 0.08
fonts: regular Inter-Regular, bold Inter-Bold, display InterDisplay-Bold  (tools/fonts)
```

`load_tokens(root=None, overrides=None)` returns the block with `fonts_abs` resolved. An episode look may override **palette entries only**: `load_tokens(overrides={"palette": {"accent": "#c0392b"}})`. Any other key, an unknown palette name or a non-hex value raises `ValueError`.

## Primitives and their spec fields

All specs also accept `type: {display, number, label, caption}` (fractions, floors enforced). `Pen`-level detail is in `common.py`.

**stats.py**
* `big_number` (full): `value` (str/number), `label`, `about`, `color`, `count_up`, `build`, `source`.
* `ratio_compare` (full): `a`, `b` = `{value, label, color?}`, `about`, `source`, `build: {a, b}`.
* `bar_compare` (full): `bars` [`{label, value, color?, text?}`] (1-6), `max`, `unit`, `build`, `source`.
* `tally` (overlay): `left`, `right` = `{label, marks, per, color?}`, `build: {left, right}`, `source`. Five-bar gates under each half; marks land one by one across the build window; the "N per M" count appears when the last mark lands; the source tag appears with the first group. A `tally-clinics` preset holds the Semmelweis spec.

**grids.py** `figure_grid` (full): `total`, `highlight` (the first K icons), `columns`, `label`, `color`, `build`, `source`.

**timelines.py** `timeline` (full): `start`, `end`, `step`, `events` [`{date, label, build, color}`] (alternate above/below the axis), `now: {from, to, build}`.

**maps.py** `map_plan` (full): `schematic` (**required, must be true**), `rooms` [`{rect, label?, fill?, minor?}`] and `routes` [`{points, build, color, label, dashed}`] in 0-1 plan coordinates. Routes draw progressively with an arrowhead; labelled routes form a legend; the SCHEMATIC tag is always drawn.

**boards.py**
* `board` (full, on the mat): `cards` [`{id, title, x, y, pin, color, build, remove, cross_out}`] with x, y the card centre as fractions of the safe box; `strings` [`{from, to, build, color}`].
* `board_card` (overlay): `title`, `pin`, `corner` (top-left/top-right/bottom-left/bottom-right), `place`, `build`. The pin slides in and settles in the corner.
* `export_card_textures(spec, out_dir, scale=2)`: one `card_<id>.png` per board card, transparent corners, for a 3D board set.

**split.py** `split` (overlay): `n` (1-6), `labels`, `gap`, `dividers`. **The video panes are composed by `tools/compose`, not here.** `layout(n, canvas, gap)` returns the pane rectangles to compose into; `labels_overlay` (registered as `split`) draws only dividers and pane labels.

**archive.py**
* `archive_mat` (full): `image`, `credit`, `highlight` `[x0,y0,x1,y1]` in image fractions, `seconds` (filled in by `render`), `push` (default 0.06). The still sits on the dark mat with a thin border and a faint paper tone; a push of 1.00 to 1.06 runs over the shot, towards the highlight if given. The credit is set on the mat under the picture; `picture_rect(spec)` returns the picture rectangle.
* `source_card` (overlay): `credit`, `at`. Outlined credit wrapped inside the margins.
* `card_lines(text, fits)` lives here; `tools/archive_ingest.card_lines` imports it.

**labels.py** (all overlays): `label` (`text`, `pos`, `color`), `callout` (`text`, `target`, `pos`), `lower_third` (`title`, `subtitle`), `underline` (`box`), `circle` (`center`, `rx`, `ry`), `date_stamp` (`text`, `at`; top-left), `day_labels` (`cycle` [[day, "first"|"second"]], `step`, `clinics`; slots at 0.3 and 0.7 of the width, the inactive one dimmed). Positions are fractions of the safe box unless noted.

**presets.py** `PRESETS` maps a name to `(primitive, spec)`: `ratio-1846`, `ward-plan-routes`, `tally-clinics`. `get_preset(name)` returns a copy.

## Encoding

`stream_to_mp4(frames, out, fps=30, canvas=(1920,1080), alpha=False)` pipes raw RGBA to ffmpeg. Opaque: H.264 yuv420p crf 18 `.mp4`. Alpha: ProRes 4444 `.mov`. It writes a temp file beside `out` and renames on success; any exception or ffmpeg failure kills ffmpeg, deletes the temp file and re-raises, so `out` is never half-written. Returns the frame count. `render_to_file(name_or_preset, spec, seconds, out, ...)` picks alpha from `OVERLAY`.

## Adding a primitive

1. Pick the family module (or add one and list it in `tools/graphics/__init__.py`).
2. Define `SCHEMA = obj({...}, required=[...])` from `spec.py`.
3. Write `static(spec, ctx)` (the unchanging layer, or `None`) and `draw(img, spec, t, ctx)`; use `ctx.font(kind)`, `ctx.col(name)`, `ctx.box`, `ctx.appear`, `Pen`.
4. `name = Primitive("name", SCHEMA, static, draw, overlay)`; add it to the module's `PRIMITIVES`, and to `OVERLAY` if transparent.
5. Add a fixture to `gallery.py`; `python/test_graphics_spec.py` then checks schema refusal, determinism, laziness and margins for it automatically. Add family tests for timing and floors.

## Gallery

`python tools/graphics/gallery.py --out sheet.png` renders every primitive mid-build and final (overlays over mid-grey) onto one contact sheet. Look at it after changing any token.

Tests: `python -m unittest discover -s python -p "test_graphics_*.py"`.
