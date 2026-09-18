# ConRol awards — parametric 3D generator 🤖

The award is the reference sculpture — a hand with the little finger raised on a
rectangular base — with the category text **engraved into its own base**. No
separate plate, so nothing to glue and nothing that can come off.

```
out/premio-<slug>.stl     × 8   one engraved sculpture per category
out/premios-8.3mf          1    the same eight, named and laid out on one plate
out/figura-referencia-100mm.stl    the blank sculpture, text-free
out/figura-punyo*.stl      4    earlier candidate figures, kept for comparison
out/peana-lisa.stl             the old pedestal, unused with the sculpture
```

`ref/mano-referencia.stl` is the source, committed so the preparation is
reproducible. `scripts/prepare_reference.py` strips the plate modelled into the
base and rescales to 100 mm.

## The sculpture

| | |
|---|---|
| Overall | **49.2 × 32.8 × 100.0 mm** |
| Base | 49.2 × 27.1 × 12.7 mm, front face **49.2 × 12.7 mm** |
| Hand | 87.3 mm tall |
| Volume | 47.9 cm³ per award |
| Mesh | ~45 000 faces, watertight, single body |

### Enlarging the base, and why it was worth it

The original base gave a face of 46.1 × 11.1 mm, which put the text at 97 % of its
ceiling: no longer name, no extra comma, no accent would fit. Enlarging only the
base — the depth is deliberately left alone — moves the capitals from
2.35/3.00/2.35 to **2.80/3.40/2.80 mm** and the stroke from 1.01 to **1.21 nozzle
widths**, for about **3 % more material** (47.9 cm³ against 46.6). The hand gives
up 1.8 % of its height so the award still stands exactly 100 mm.

### The plate, if you ever want it

`EMIT_PLATES = True` also writes a 49 × 12.7 mm plate to glue on. It is off by
default: a plate has to fill the whole face to hold three lines, which makes it
visually identical to engraving, minus the glue.

## Categories

Three lines per award, fixed order: the event, the award name, the line that
lands the joke.

| Slug | Name | Phrase |
|---|---|---|
| `aportacio` | SANCHO PANZA | SIN TI, NO HAY CONROL |
| `refinament` | REFINAMIENTO | DEL GESTO |
| `dramaqeen` | DRAMAQEEN | LLORA SIN FRENO |
| `abuelo-cebolleta` | ABUELO/A CEBOLLETA | ANTES, TODO ERA MEJOR |
| `intensito` | INTENSITO | EVANGELIZA CON PASIÓN |
| `neurotipico` | NEUROTÍPICO | ÚNICO EN EL ROL |
| `molusco-bivalvo` | MOLUSCO BIVALVO | LO VIVE POR DENTRO |
| `troll-cavernas` | TROLL CAVERNAS | TERROR DE LA NOCHE |

`refinament` reconstructs the reference plate's title — *EL REFINAMIENTO DEL
GESTO* — across the name and phrase lines.

### Two traps the layout had to survive

**Descenders and accents cost height.** A comma drops 0.53 mm below the baseline
and an accent rises 0.64 mm above the capital, and either one inflates the block.
Worse, a **Q** in a name costs 0.5 mm: that is why the earlier draft phrase
*"LLORA Y QUE SE NOTE"* had to go. When writing new lines, avoid Q, J, G, P, and
watch commas.

**Capitals are a maximum, not a promise.** Stacking shrinks them, per category,
until the block clears a 1.0 mm margin at both edges. So `intensito` (one accent)
renders at 99.6 % and `neurotipico` (two accents) at 91 %, while the rest keep
full size. The verification reports the size actually used and marks the shrunk
ones.

### Legibility, derived rather than guessed

The font's stroke is 0.172 of the capital height, measured from the 'I' at
runtime, so the floor follows from the nozzle:

| Nozzle | Minimum stroke | Minimum capital height |
|---|---|---|
| 0.25 mm | 0.29 mm | 1.42 mm |
| 0.4 mm | 0.46 mm | 2.33 mm |
| 0.6 mm | 0.69 mm | 3.40 mm |

The engraved lines run at 0.44–0.59 mm of stroke, i.e. **1.10 to 1.47 nozzle
widths at 0.4 mm**. That is the whole reason the base was enlarged.

## Why one STL per award, and why that is fine

An STL is a triangle soup: no objects, no names, no units, no parameters. Text
engraved into the base is baked into the triangles, so **different text means a
different file**. That is unavoidable, and it is not a problem:

| | Engraved | Glued plate |
|---|---|---|
| Sculptures to print | 8 | 8 |
| Material for sculptures | same | same |
| Extra parts | **0** | 8 |
| Gluing operations | **0** | 8 |
| Can come off | **no** | yes |

Engraving costs the same material and time and removes eight parts and eight
gluing operations. What it does cost is the slicer's "multiply ×8", because every
object is unique — which is what `premios-8.3mf` is for.

### Why 3MF rather than an STL with eight bodies

`out/premios-8.3mf` (6.4 MB) holds all eight awards as **named objects** with
millimetre units, already laid out on one plate — one slice, one print run. In STL
the same eight would be ~360 000 triangles in a blob, with no way to tell which is
which.

## Usage

```bash
uv venv --python 3.12
uv pip install trimesh svgelements fonttools numpy shapely manifold3d scipy networkx matplotlib lxml rtree

.venv/bin/python scripts/prepare_reference.py     # strip the plate, enlarge the base, scale to 100 mm
.venv/bin/python scripts/build_premios.py         # engrave every award, write out/*.stl and the 3MF
.venv/bin/python scripts/verify_text_geometry.py  # text, base, hollowing
.venv/bin/python scripts/verify_figure.py         # the earlier candidate figures, plus the preview
```

| Script | Role |
|---|---|
| `scripts/geometry_common.py` | Shared primitives: boxes, frustums, chamfered rectangles, extrusion |
| `scripts/prepare_reference.py` | Strips the modelled plate, enlarges the base, rescales |
| `scripts/build_premios.py` | Categories, text layout, engraving, exports |
| `scripts/fist_figure.py` etc. | The four earlier candidate figures, kept for comparison |
| `scripts/verify_text_geometry.py` | Independent verification of text and base |
| `scripts/verify_figure.py` | Verification of the earlier figures and their preview |

## Honest print budget

**Model volume is not print cost.** At 15 % infill a slicer uses well under the
model volume, so the build script prints the estimate both ways rather than
letting model volume pass for print cost.

Measured model volumes, per award:

| Part | Volume | Filament (est.) |
|---|---|---|
| Engraved sculpture | 47.9 cm³ | ~19 cm³ |
| Base alone | ~17 cm³ | — |

For a full set of eight: **~383 cm³ of model, roughly 155 g of PLA**, plus print
time. Only the volumes are measured; filament and time are estimates from stated
assumptions and depend on the machine. The figures dominate, and at 100 mm tall
each one is a long print — ask your friend to slice one before committing to
eight.

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

`verify_figure.py` runs all of these on **all four** versions with the same code.

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
