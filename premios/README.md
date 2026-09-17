# ConRol awards — parametric 3D generator 🤖

Generates the complete ConRol 2026 award from code: **a closed fist with the
pinky raised, on a hollowed pedestal, with the category text on a plaque.**

| Output | What it is | Print |
|---|---|---|
| `out/figura-punyo.stl` | The fist. Same figure for every award. | once per award |
| `out/peana-lisa.stl` | Plain hollowed pedestal. Same pedestal for every award. | once per award |
| `out/placa-<slug>.stl` | Engraved plaque, one per category. | one per award |
| `out/previews/figura-vistas.png` | Flat-shaded orthographic views of the figure | — |

**Route: plaque.** One pedestal design, one plaque per award. The plaque can be a
contrasting colour, a botched engraving wastes 3.6 cm³ instead of 25, and only
one pedestal has to be printed and verified. Set `ROUTE = "engraved"` to engrave
the text straight onto each pedestal instead. Do not mix the two on the same
pedestal: it would print the text twice.

## The figure

A geometric, minimalist fist — modelled as a solid, not sculpted. The styling is
what makes it buildable from primitives, but the anatomy is still readable:

- **four finger columns** across the front face, separated by three vertical
  grooves that also cut the top edge, so they read as knuckles from above
- **the thumb**, a single angled block crossing the lower front
- **a wrist** flaring out of the tenon into the body
- **the pinky**, the outermost finger column, rising 26 mm clear of the fist and
  leaning 5° outward

**Look at `out/previews/figura-vistas.png` before approving it.** The geometry is
verified by machine (see below), but whether it *reads* as a fist is a judgement
call that only a human can make. Iterate on the constants in
`scripts/fist_figure.py` and re-run.

| Figure dimension | Value |
|---|---|
| Body | 40 × 30 × 38 mm |
| Overall (with pinky) | 41.5 × 35 × 79.9 mm |
| Pinky | 9 × 9 mm, 26 mm tall |
| Tenon | 30 × 22 × 5.7 mm |
| Award height assembled | **100 mm** |

## Geometry

| Part | Size (mm) | Notes |
|---|---|---|
| Pedestal | 72 × 34 × 26 | Mortise 30.5 × 22.5 × 6 mm on top, hollowed from below |
| Plaque | 68 × 2.5 × 22 | Fits the pedestal front face with 2 mm to spare |
| Type | Liberation Sans Narrow Bold | Title cap 4.2 mm, subtitle 3.0 mm, body 2.8 mm |

The figure does **not** sit in a thin slot: a three-dimensional fist needs a
footprint it can stand in. The mortise (socket) gives the joint shear strength
so the figure cannot be knocked off sideways, with 0.25 mm of clearance per side
so the tenon actually drops in on a real printer. Glue it once it is seated.

### Categories

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

## Usage

```bash
uv venv --python 3.12
uv pip install trimesh svgelements fonttools numpy shapely manifold3d scipy networkx matplotlib

.venv/bin/python scripts/build_premios.py          # writes out/*.stl
.venv/bin/python scripts/verify_text_geometry.py   # text, pedestal, hollowing
.venv/bin/python scripts/verify_figure.py          # the fist, plus the preview PNG
```

| Script | Role |
|---|---|
| `scripts/geometry_common.py` | Shared primitives: boxes, rectangular frustums |
| `scripts/fist_figure.py` | The fist. All its dimensions live in one frozen dataclass |
| `scripts/build_premios.py` | Categories, text layout, pedestal, plaque, export |
| `scripts/verify_text_geometry.py` | Independent verification of text and parts |
| `scripts/verify_figure.py` | Verification of the fist and the renders |

## Honest print budget

**Model volume is not print cost.** This distinction bit an earlier version of
this document, which claimed hollowing the pedestal saved 45% of material
because the model volume dropped from 63.6 to 34 cm³. It does not: at 15% infill
a slicer printing the *solid* block would have used roughly 21 cm³ of filament
anyway. The build script now prints the estimate both ways so the mistake cannot
be repeated silently.

Measured model volumes and estimated filament ranges:

| Part | Model volume | Estimated filament |
|---|---|---|
| Pedestal (hollow, 1.8 mm walls) | 25.0 cm³ | ~25 cm³ — thin walls print solid |
| Figure (chunky solid) | 61.3 cm³ | ~21 cm³ — the slicer infills it |
| Plaque | 3.6 cm³ | ~3.6 cm³ |

So **why keep the hollow?** Because it is not about saving filament. It buys an
open pocket holding 34.5 cm³ that you can fill with sand (~55 g). A 100 mm figure
on a 25 g base tips over the first time someone brushes the table, and ballast is
the only thing that fixes it. Getting the same weight from infill would mean
printing near solid, which costs far more than the 4 cm³ the pocket costs.

For a full set of seven awards:

| Item | Filament | Print time (estimate) |
|---|---|---|
| 7 × pedestal | ~175 cm³ ≈ 205 g | ~10–17 h |
| 7 × figure | ~147 cm³ ≈ 172 g | **~21–42 h** |
| 7 × plaque | ~25 cm³ ≈ 30 g | ~2–3 h |
| **Total** | **~350 cm³ ≈ 410 g** | **~35–60 h** |

The figures dominate: 80 mm at 0.2 mm layers is ~400 layers each. Only the
volumes are measured; filament and time are estimates from stated assumptions
(15% infill, 1.26 mm of perimeters) and the real numbers depend on the machine.
Ask the friend to slice one figure and one pedestal before promising anything.

## What the verification actually proves

Both scripts exit non-zero on failure. Run them after any change.

`verify_text_geometry.py`

1. **Glyph geometry vs an independent rendering.** Every test glyph is compared
   against `matplotlib.textpath` (FreeType), which shares no code with the
   fontTools → svgelements → shapely pipeline. Result: IoU ≥ 0.99, ink area
   within 0.3 %. Mirrored and flipped variants act as controls, and the script
   reports how many glyphs can actually discriminate orientation (near-symmetric
   ones such as `O` cannot, and are not counted as proof).
2. **Material removal**: analytic volume (solid − socket − cavity − ink × depth)
   must match the mesh. Catches cutters that escape the part and cut in thin air.
3. **Layout** for all seven categories on both parts: every line fits the width,
   no line falls below the 2.5 mm legibility floor, the block keeps a 1.5 mm
   margin from both edges, and the reading order holds.
4. **Hollowing**: wall thickness, socket-floor clearance, and that the cavity is
   open at the bottom rather than an unprintable sealed void.

`verify_figure.py`

1. Single watertight solid, positive volume, consistent winding.
2. **It reads as a fist**: exactly four finger fronts counted as disjoint regions
   in a slab cut through the groove depth, a single region above the knuckles,
   the pinky close to its nominal cross-section, thick enough and high enough.
3. **It fits the pedestal**: tenon clearance, socket-floor material, and that the
   assembled award is the intended height.
4. The render convention puts the pinky up and to the right, so the preview
   cannot be silently mirrored or upside down.
5. The preview actually rendered — it has ink, the shading varies, and all three
   panels drew something.

### What is *not* proven

No STL here has been **sliced or printed**. Watertight, single-shell,
positive-volume meshes are a necessary condition, not a guarantee. The renders
are for silhouette and read only, not surface finish. The first real print is the
acceptance test: print one figure and one pedestal before committing to seven.

### Mechanical warning

A raised pinky is a rod in bending, which is the worst case for FDM. At this
scale it is 9 mm thick, so it is not fragile — but **print the figure lying down
or tilted**, not with the pinky running up the Z axis, or the layer planes sit
across the bending load and the pinky delaminates under a knock. PETG or PLA+
over resin if the awards will be handled.
