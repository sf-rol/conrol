# ConRol awards — parametric 3D generator 🤖

Generates the complete ConRol 2026 award from code: **a closed fist with the
pinky raised, on a hollowed pedestal, with the category text on a plaque.**

| Output | What it is | Print |
|---|---|---|
| `out/figura-punyo.stl` | **V1.** Plain geometric fist. | one per award |
| `out/figura-punyo-cubista.stl` | **V2.** Faceted, cubist fist. | one per award |
| `out/figura-punyo-elegante.stl` | **V3.** Tapered, articulated fist built to the brief. | one per award |
| `out/peana-lisa.stl` | Plain hollowed pedestal. Same pedestal for every award. | once per award |
| `out/placa-<slug>.stl` | Engraved plaque, one per category. | one per award |
| `out/previews/figura-comparativa.png` | All three figures, side by side, same scale | — |

Print **one** figure version, not all three: they share the socket, so any of
them fits the same pedestal.

**Route: plaque.** One pedestal design, one plaque per award. The plaque can be a
contrasting colour, a botched engraving wastes 3.6 cm³ instead of 25, and only
one pedestal has to be printed and verified. Set `ROUTE = "engraved"` to engrave
the text straight onto each pedestal instead. Do not mix the two on the same
pedestal: it would print the text twice.

## Three candidate figures

All three are a closed fist with the pinky raised, modelled as a solid rather
than sculpted. They share the socket and the 100 mm assembled height, so they are
directly comparable — and any of them fits the same pedestal.

`DESIGN-BRIEF.md` is the sculptural brief that version 3 was built from; versions
1 and 2 predate it and are kept for comparison.

**Look at `out/previews/figura-comparativa.png` before choosing.** The geometry is
verified by machine (see below), but whether it *reads* as a fist — and as a
*pinky* — is a judgement call only a human can make. Iterate on the constants in
the scripts and re-run.

### Version 1 — plain geometric (`fist_figure.py`)

40 × 30 × 38 mm body, four finger columns separated by three identical grooves,
a thumb block, a flared wrist, and a pinky rising 26 mm at the outer edge.
116 faces, deliberately blocky.

### Version 3 — tapered and articulated (`fist_elegant.py`)

Built from scratch to `DESIGN-BRIEF.md`, with two things the earlier versions
lack:

- **It tapers.** A hand is narrow at the wrist and widest across the knuckles. The
  body is a stack of chamfered sections interpolated along an anatomical profile
  (`BODY_PROFILE`), so the silhouette swells and the facets follow it. Every
  section is a vertical prism, so each step is under a millimetre and needs no
  support, while still reading as a faceted sweep rather than a smooth surface.
- **It articulates at two rows**, not one: three knuckles along the sloping top
  and a second row of proximal interphalangeal joints below them. A fist with one
  row of bumps reads as a box.

The pinky is three phalanges with a flexion at every joint — `+8°`, `−5°`, `−6°` —
so it forms the shallow S-curve of a real extended little finger rather than a
stiff rod. The thumb is two segments with its own joint, and there is a
hypothenar pad on the little-finger side of the palm.

The taper also makes it **the cheapest of the three**: 44.4 cm³ against 61–62 cm³,
about 28 % less material for the same award.

| | V1 plain | V2 cubist | V3 tapered |
|---|---|---|---|
| Body | 40 × 30 × 38 mm | 40 × 30 × 38 mm | tapers 30 → 38 mm wide |
| Overall | 41.5 × 35 × 79.9 | 42.4 × 34 × 79.8 | 39.2 × 31.1 × 78.8 |
| Knuckle rows | 1 | 1 | **2** |
| Pinky | 9 mm, straight | 8.6 mm, 2 offset segments | 8 mm, 3 phalanges, flexed |
| Pinky axis bow | 0.00 mm | 0.17 mm | **0.51 mm** |
| Model volume | 61.3 cm³ | 62.5 cm³ | **44.4 cm³** |
| Faces | 116 | 868 | 1626 |

### Making the raised finger read as the pinky

Styling is not allowed to cost this, so it is carried deliberately:

1. **Three knuckles, and the pinky column left bare.** Three knuckles and then a
   raised finger makes that finger the fourth one along. `verify_figure.py`
   measures it: above the fist there are four separate regions, three of them on
   the thumb side of the pinky column and exactly one beyond it.
2. **The thumb is on the opposite side**, which fixes the handedness.
3. **The pinky is the narrowest column** and the only digit articulated into
   visible segments above the fist, because the pinky is the small finger.
4. In V3 the knuckle line **descends towards the pinky**, so the little finger
   knuckle sits lowest and has further to travel to stand proud.

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
.venv/bin/python scripts/verify_figure.py          # both fists, plus the comparison PNG
```

| Script | Role |
|---|---|
| `scripts/geometry_common.py` | Shared primitives: boxes, frustums, chamfered rectangles, extrusion |
| `scripts/fist_figure.py` | Version 1. All its dimensions in one frozen dataclass |
| `scripts/fist_cubist.py` | Version 2. Same, plus the cubist devices |
| `scripts/fist_elegant.py` | Version 3. Built to `DESIGN-BRIEF.md` |
| `scripts/build_premios.py` | Categories, text layout, pedestal, plaque, exports |
| `scripts/verify_text_geometry.py` | Independent verification of text and parts |
| `scripts/verify_figure.py` | Verification of **both** figures and the comparison sheet |

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
| Figure v1 (chunky solid) | 61.3 cm³ | ~21 cm³ — the slicer infills it |
| Figure v2 (chunky solid) | 62.5 cm³ | ~21 cm³ |
| Figure v3 (tapered solid) | 44.4 cm³ | ~17 cm³ |
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
| 7 × figure (either version) | ~147 cm³ ≈ 172 g | **~21–42 h** |
| 7 × plaque | ~25 cm³ ≈ 30 g | ~2–3 h |
| **Total** | **~350 cm³ ≈ 410 g** | **~35–60 h** |

Either figure version costs about the same as the other; version 2 is 1.2 cm³
heavier in the model, which is inside the noise of the estimate. Print one of
each only if you want to hold both before deciding.

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

`verify_figure.py` runs the same checks on **both** versions, so their
differences are real differences and not differences in how hard they were
measured.

1. Single watertight solid, positive volume, consistent winding.
2. **Four fingers**: three notches found as peaks in the front-most Y as a
   function of X. Counting peaks works for square and wedge grooves alike, and
   does not depend on slicing exactly inside a groove.
3. **Knuckles**: one separate region per knuckle plus the pinky, every knuckle on
   the thumb side of the pinky column, exactly one raised finger beyond them.
4. **The pinky**: alone above the fist, section within 25 % of nominal, thick
   enough, high enough, and the thumb protruding past the front face. Where a
   version declares a jointed pinky, its axis must **bow at least 0.35 mm off the
   straight chord** — measured 0.00 mm for V1's straight finger, 0.17 mm for V2's
   offset segments, 0.51 mm for V3's flexed phalanges. The brief asks for a
   *perceptible* flexion, so it is measured rather than asserted.
5. **The socket**: tenon clearance, socket-floor material, and that the assembled
   award is the intended height.
6. The render convention puts the pinky up and on the right, so the preview
   cannot be silently mirrored or upside down.
7. The comparison sheet has ink, its shading varies, and every model row drew
   something — a blank image would otherwise pass silently.

`verify_figure.py` runs all of these on **all three** versions with the same code.

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
