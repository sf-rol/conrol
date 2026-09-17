# ConRol awards — parametric 3D generator 🤖

Generates the printable parts of a ConRol award from code:

| Output | What it is |
|---|---|
| `out/peana-<slug>.stl` | Pedestal with the category text engraved on its front face and a slot on top for a flat figure |
| `out/placa-<slug>.stl` | Standalone engraved plaque (glue it on, or use it as a nameplate) |

The **figure is not here yet**. See [Figure: what is still missing](#figure-what-is-still-missing).

## Why code and not an SVG

SVG is 2D. A 3D printer needs a closed solid (STL/3MF). A silhouette can be
extruded into a solid part, and that is what this repo does for text: the
category name is traced from a real font, extruded, and boolean-subtracted from
the pedestal to engrave it. Nothing is drawn by hand, so every category is a
one-line change.

## Current geometry

| Part | Size (mm) | Notes |
|---|---|---|
| Pedestal | 72 × 32 × 16 | Slot 46 × 2.6 × 7 mm on top; engraving 0.7 mm deep |
| Plaque | 70 × 2.5 × 16 | Engraving 0.7 mm deep |
| Type | Liberation Sans Narrow Bold | Title cap 4.2 mm, subtitle 3.2 mm |

With an 84 mm figure in the slot the award stands about 100 mm tall.

## Usage

```bash
uv venv --python 3.12
uv pip install trimesh svgelements fonttools numpy shapely manifold3d scipy networkx matplotlib

.venv/bin/python scripts/build_premios.py          # writes out/*.stl
.venv/bin/python scripts/verify_text_geometry.py   # proves the geometry is right
```

### Adding or renaming a category

Edit `CATEGORIES` in `scripts/build_premios.py` and re-run the build. The title
is auto-fitted to the available width, so a long name shrinks rather than
overflowing.

```python
CATEGORIES = [
    Category(slug="millor-narrativa", title="MEJOR NARRATIVA", subtitle="ConRol 2025"),
    Category(slug="millor-interpretacio", title="MEJOR INTERPRETACIÓN", subtitle="ConRol 2025"),
]
```

### Changing dimensions

Both parts are frozen dataclasses (`Pedestal`, `Plaque`) at the top of the
build script. Note that `title_z` / `subtitle_z` are the vertical centres of the
engraved lines, and a line that leaves the part is rejected at build time.

## What the verification actually proves

`scripts/verify_text_geometry.py` runs three checks and exits non-zero on
failure. Run it whenever you change a dimension or a font.

1. **Glyph geometry vs an independent rendering.** Each glyph is compared
   against `matplotlib.textpath` (FreeType), which shares no code with the
   fontTools → svgelements → shapely pipeline. Result: IoU ≥ 0.99, ink area
   within 0.3 %. Mirrored and flipped variants are used as controls, and the
   script reports how many test glyphs can actually discriminate orientation
   (near-symmetric ones like `O` cannot, and are not counted as proof).
2. **Material removal**, for both parts: the analytic volume
   (solid − slot − ink × depth) must match what trimesh reports, and no cutting
   solid may escape the part.
3. **Layout**: engraved width within the available width, capital height above
   the 2.5 mm legibility floor, and the title never rendered smaller than the
   subtitle.

### What is *not* proven

The STLs have **never been sliced or printed**. Watertight, single-shell,
positive-volume meshes are a necessary condition, not a guarantee. The first
real print is the actual acceptance test. Print one before committing to twenty.

## Figure: what is still missing

The award figure is a **closed fist with the pinky raised** — a sculptural
problem, not a flat one. Options, from cheapest to best:

| Route | Where to look | Notes |
|---|---|---|
| Extruded silhouette | This repo can do it | Reads instantly as an icon, prints without supports, very robust. Loses all volume. |
| Find an existing model | Printables, MakerWorld, Thingiverse, **Thangs** (aggregator), Cults3D, MyMiniFactory, Sketchfab (filter *downloadable*), CGTrader, TurboSquid | Search terms: `pinky up`, `pinky promise hand`, `hand pinky`, `tea drinker hand`, `posh hand`, `snob hand`, `hand gesture`. Check the licence before using it on a gift. |
| Sculpture scans | **Scan the World** (on MyMiniFactory), Smithsonian Open Access | Real museum hands; you would still have to repose the pinky. |
| Photogrammetry | 60–80 photos + Meshroom (free) or Polycam | Gives you *your own* fist, which is the actual joke. Most personal, most work. |
| Image → 3D | Meshy, Tripo, Rodin | Fast, dirty topology, check the licence. |
| Sculpt it | Blender | Full control, needs someone who can sculpt. |

### Mechanical warning

A raised pinky is a thin rod in bending — the worst case for FDM. Mitigations,
in order of how much they help:

- **Do not print it small.** At a 100 mm award the pinky is about 7.5 mm across
  and survives a drop; at 50 mm it is 4 mm and snaps. Never below ~80 mm.
- **Print it lying down or tilted.** Pinky pointing up along Z puts the layer
  planes across the bending load and it delaminates.
- **Wide, low, heavy base.** The slot is 46 × 2.6 mm, so the silhouette must fit
  that. Fill the base hollow with a bolt if you can.
- **PETG or PLA+ over resin** if the award will be handled. Resin gives detail
  and breaks on impact.

### Slot interface

The figure must fit the pedestal slot: **≤ 46 mm wide at its base, 2.6 mm thick,
7 mm deep**. Anything thicker needs a wider slot — change `slot_width` in
`Pedestal` and re-run.
