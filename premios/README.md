# ConRol awards — parametric 3D generator 🤖

Generates the printable parts of the ConRol 2026 awards from code.

| Output | What it is |
|---|---|
| `out/peana-lisa.stl` | Plain pedestal, shared by every award. Print one per award. |
| `out/placa-<slug>.stl` | Engraved plaque, one per category. Glue it onto the pedestal. |

**Route: plaque.** One pedestal design, one plaque per award. The plaque can be a
contrasting colour, a botched engraving wastes 3.6 cm³ instead of 34, and only
one pedestal has to be printed and verified. Set `ROUTE = "engraved"` in the
build script to engrave the text straight onto each pedestal instead — no
assembly, but one file per award and every failure costs a full pedestal. Do not
mix the two on the same pedestal: it would print the text twice.

The **figure is not here yet**. See [Figure: what is still missing](#figure-what-is-still-missing).

## Why code and not an SVG

SVG is 2D. A 3D printer needs a closed solid (STL/3MF). A silhouette can be
extruded into a solid part, and that is what this repo does for text: the award
lines are traced from a real font, extruded, and boolean-subtracted to engrave
them. Nothing is drawn by hand, so a new category is a one-line change.

## Categories

| Slug | Title | Subtitle | Body |
|---|---|---|---|
| `aportacio` | ConRol 2026 | POR APORTAR UNA ACTIVIDAD | PORQUE SIN TI / ESTO NO VUELVE A LATIR |
| `dramaqeen` | DRAMAQEEN | ConRol 2026 | POR BUSCAR EL DRAMA / INFINITO E INTENSO |
| `abuelo-cebolleta` | ABUELO/A CEBOLLETA | ConRol 2026 | PORQUE EN MIS TIEMPOS / ESTO MOLABA MÁS |
| `intensito` | INTENSITO | ConRol 2026 | POR TOMÁRSELO TODO / MUY EN SERIO |
| `neurotipico` | NEUROTÍPICO | ConRol 2026 | POR SER EL NORMALITO / DE LA MESA |
| `molusco-bivalvo` | MOLUSCO BIVALVO | ConRol 2026 | POR SENTIRLO TODO / POR DENTRO |
| `troll-cavernas` | TROLL DE LAS CAVERNAS | ConRol 2026 | POR RONCAR COMO UN / MONSTRUO ÉPICO |

The `aportacio` award is given once per contributor, so its plaque is reprinted
as needed. Body lines are pre-wrapped on purpose: the plate does not word-wrap,
so a line that is too long gets scaled down instead of broken.

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

Measured mesh volumes, per award:

| Part | Volume | Print time (est.) |
|---|---|---|
| Pedestal | 34.1 cm³ | ~2–3 h |
| Plaque | 3.6 cm³ | ~25 min |

So **~38 cm³ and ~3 h per award**, plus the figure. Because one pedestal design
serves every award, adding an award later costs one more pedestal and one more
plaque — nothing has to be redesigned.

For a set of seven, excluding figures: roughly **260–300 g of PLA and 20–25 h**.
Filament and time are **estimates**; only the volumes are measured.

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
