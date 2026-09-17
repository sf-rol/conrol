# ConRol awards — parametric 3D generator 🤖

Generates the printable parts of the ConRol 2026 awards from code.

| Output | What it is |
|---|---|
| `out/peana-<slug>.stl` | Pedestal with the award text engraved on its front face and a slot on top for the figure. One per category. |
| `out/placa-<slug>.stl` | The same text on a thin plate, to glue onto a plain pedestal. One per category. |
| `out/peana-lisa.stl` | Plain pedestal. Use this with the plaques. One file, valid for every award. |

**Two routes, pick one per award — do not mix them on the same pedestal:**
engraving the pedestal *and* gluing a plaque over it prints the text twice.

- **Engraved route**: print `peana-<slug>.stl`. No assembly, no glue.
- **Plaque route**: print `peana-lisa.stl` + `placa-<slug>.stl`. The plaque can be
  a different colour, reads better than an engraving, and if a plaque comes out
  badly you have wasted 3 g instead of 34 g.

The **figure is not here yet**. See [Figure: what is still missing](#figure-what-is-still-missing).

## Why code and not an SVG

SVG is 2D. A 3D printer needs a closed solid (STL/3MF). A silhouette can be
extruded into a solid part, and that is what this repo does for text: the award
lines are traced from a real font, extruded, and boolean-subtracted to engrave
them. Nothing is drawn by hand, so a new category is a one-line change.

## Categories

| Slug | Title | Subtitle | Body |
|---|---|---|---|
| `aportacio` | ConRol 2026 | POR APORTAR UNA ACTIVIDAD | GRACIAS POR REMOVER / EL CALDERO |
| `dramaqeen` | DRAMAQEEN | ConRol 2026 | POR BUSCAR EL DRAMA / INFINITO E INTENSO |
| `abuelo-cebolleta` | ABUELO/A CEBOLLETA | ConRol 2026 | PORQUE EN MIS TIEMPOS / ESTO MOLABA MÁS |
| `intensito` | INTENSITO | ConRol 2026 | POR TOMÁRSELO TODO / MUY EN SERIO |
| `neurotipico` | NEUROTÍPICO | ConRol 2026 | POR SER EL NORMALITO / DE LA MESA |
| `molusco-bivalvo` | MOLUSCO BIVALVO | ConRol 2026 | POR SENTIRLO TODO / POR DENTRO |
| `troll-cavernas` | TROLL DE LAS CAVERNAS | ConRol 2026 | POR RONCAR COMO UN / MONSTRUO ÉPICO |

The `aportacio` phrase is a **placeholder awaiting Yachar's choice**. Body lines
are pre-wrapped on purpose: the plate does not word-wrap, so a line that is too
long gets scaled down instead of broken.

## Geometry

| Part | Size (mm) | Notes |
|---|---|---|
| Pedestal | 72 × 34 × 26 | Slot 46 × 2.6 × 8 mm on top; hollowed from below |
| Plaque | 68 × 2.5 × 22 | Fits the pedestal front face with 2 mm to spare |
| Type | Liberation Sans Narrow Bold | Title cap 4.2 mm, subtitle 3.0 mm, body 2.8 mm |

### Hollowing

A solid 26 mm block is 63.6 cm³ of filament, which across a full set of awards
is tens of hours of printing. The pedestal is therefore hollowed from below:
2.4 mm walls, an open bottom (a sealed internal void is not printable on an FDM
machine), and a roof that tapers at 45° so it needs no supports. That removes
**45 % of the material**: 33.9 cm³ instead of 63.6 cm³.

The cavity is also a pocket for weighting the award with sand or a bolt, and it
is held 3 mm clear of the figure slot, because a figure that wobbles in the
pocket would crack through a thinner floor.

## Usage

```bash
uv venv --python 3.12
uv pip install trimesh svgelements fonttools numpy shapely manifold3d scipy networkx matplotlib

.venv/bin/python scripts/build_premios.py          # writes out/*.stl
.venv/bin/python scripts/verify_text_geometry.py   # proves the geometry is right
```

### Adding or renaming a category

Edit `CATEGORIES` in `scripts/build_premios.py` and re-run. Titles auto-fit the
available width, so a long name shrinks rather than overflowing.

### Changing dimensions

`Pedestal`, `Plaque` and `TextLayout` are frozen dataclasses at the top of the
build script. A line that would leave the part is rejected at build time.

## What the verification actually proves

`scripts/verify_text_geometry.py` runs four checks and exits non-zero on failure.
Run it whenever you change a dimension, a font or a category.

1. **Glyph geometry vs an independent rendering.** Every test glyph is compared
   against `matplotlib.textpath` (FreeType), which shares no code with the
   fontTools → svgelements → shapely pipeline. Result: IoU ≥ 0.99, ink area
   within 0.3 %. Mirrored and flipped variants act as controls, and the script
   reports how many glyphs can actually discriminate orientation (near-symmetric
   ones such as `O` cannot, and are not counted as proof).
2. **Material removal**: analytic volume (solid − slot − cavity − ink × depth)
   must match the mesh, and no cutting solid may escape the part.
3. **Layout**, for all seven categories on both parts: every line fits the width,
   no line falls below the 2.5 mm legibility floor, the block keeps a 1.5 mm
   margin from both edges, and the reading order holds (title ≥ subtitle ≥ body).
4. **Hollowing**: wall thickness, slot-floor clearance, and that the cavity is
   open at the bottom rather than an unprintable sealed void.

### What is *not* proven

The STLs have **never been sliced or printed**. Watertight, single-shell,
positive-volume meshes are a necessary condition, not a guarantee. The first
real print is the actual acceptance test. Print one before committing to seven.

## Print budget

Verified volumes, per award:

| Part | Solid volume | Notes |
|---|---|---|
| Pedestal | 33.9 cm³ | already hollowed |
| Plaque | 3.6 cm³ | ~25 min |

Estimated for a full set of seven (filament and time are **estimates**, not
measurements): roughly **250–300 g of PLA and 18–25 h** for bases and plaques.
The figures are the real cost, not the bases — see below.

## Figure: what is still missing

The award figure is a **closed fist with the pinky raised** — a sculptural
problem, not a flat one. Options, cheapest to best:

| Route | Where to look | Notes |
|---|---|---|
| Extruded silhouette | This repo can do it | Reads instantly as an icon, prints without supports, very robust. Loses all volume. |
| Find an existing model | Printables, MakerWorld, Thingiverse, **Thangs** (aggregator), Cults3D, MyMiniFactory, Sketchfab (filter *downloadable*), CGTrader, TurboSquid | Search terms: `pinky up`, `pinky promise hand`, `hand pinky`, `tea drinker hand`, `posh hand`, `snob hand`, `hand gesture`. Check the licence before using it on a gift. |
| Sculpture scans | **Scan the World** (on MyMiniFactory), Smithsonian Open Access | Real museum hands; you would still have to repose the pinky. |
| Photogrammetry | 60–80 photos + Meshroom (free) or Polycam | Gives you *your own* fist, which is the actual joke. Most personal, most work. |
| Image → 3D | Meshy, Tripo, Rodin | Fast, dirty topology, check the licence. |
| Sculpt it | Blender | Full control, needs someone who can sculpt. |

### Print cost of the figure

This dominates everything else. A 84 mm figure at 0.2 mm layers is about 420
layers, so expect **4–8 h per figure**: seven of them is **30–55 h of printer
time**. Ask the friend for a real estimate on their machine before promising
anything, and consider a fallback tier that is only the plaque.

### Mechanical warning

A raised pinky is a thin rod in bending — the worst case for FDM. Mitigations,
in order of how much they help:

- **Do not print it small.** At a 100 mm award the pinky is about 7.5 mm across
  and survives a drop; at 50 mm it is 4 mm and snaps. Never below ~80 mm.
- **Print it lying down or tilted.** Pinky pointing up along Z puts the layer
  planes across the bending load and it delaminates.
- **Keep the base heavy.** Fill the cavity with sand or a bolt.
- **PETG or PLA+ over resin** if the award will be handled. Resin gives detail
  and breaks on impact.

### Slot interface

The figure must fit the pedestal slot: **≤ 46 mm wide at its base, 2.6 mm thick,
8 mm deep**. Anything thicker needs a wider slot — change `slot_width` in
`Pedestal` and re-run.
