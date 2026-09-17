#!/usr/bin/env python3
"""Prove the generated award geometry is correct, without relying on eyeballing.

Three checks. None of them uses the code under test as its own reference.

1. Glyph shape, scale and fill rule. Each glyph is rasterised twice: once from
   the geometry this repo builds (fontTools + svgelements + shapely) and once
   from matplotlib's FreeType path (TextPath), which shares no code with it.
   Both sit at the same pen origin and scale, so a correct result must overlap
   almost perfectly. Mirroring and flipping the geometry act as controls: for
   asymmetric glyphs the control must score clearly worse, otherwise the test
   proves nothing. Near-symmetric glyphs (O, o, E) cannot discriminate
   orientation at all and are reported as such instead of being counted as proof.

2. Material removal, for the pedestal and the plaque: the analytic volume
   (solid - slot - ink x depth) must match what trimesh reports, and no cutting
   solid may escape the part.

3. Layout, for every configured category on both parts: every line fits the
   available width, no line is smaller than the legibility floor, the stacked
   block keeps a margin from both edges, and the reading order is preserved
   (title never smaller than subtitle, subtitle never smaller than body).

Usage:  .venv/bin/python scripts/verify_text_geometry.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import shapely
import shapely.affinity
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_premios import (  # noqa: E402
    CATEGORIES,
    FONT_PATH,
    Category,
    GlyphFont,
    Pedestal,
    Plaque,
    build_pedestal,
    build_plaque,
    pedestal_cavity,
    stack_lines,
)

GRID = 260
MIN_CAP_MM = 2.5  # hard legibility floor for a 0.4 mm nozzle
COMFORT_CAP_MM = 2.8  # below this the strokes get marginal; reported, not enforced
MIN_EDGE_MARGIN_MM = 1.5
TEST_CHARS = "MEORAÓ2o5"
REFERENCE_CAP_EM = 0.688  # starting guess for cap height / em
CONTROL_IS_UNINFORMATIVE = 0.90
FONT_PROP = FontProperties(fname=str(FONT_PATH))


# --------------------------------------------------------------------------- 1


def reference_glyph(char: str, size: float) -> TextPath:
    """Independent glyph outline via matplotlib/FreeType, pen origin at (0, 0)."""
    return TextPath((0, 0), char, size=size, prop=FONT_PROP)


def calibrate_size(cap_mm: float) -> float:
    """Em size in TextPath units that yields the requested capital height."""
    size = cap_mm / REFERENCE_CAP_EM
    for _ in range(3):
        height = reference_glyph("H", size).get_extents().height
        if height <= 0:
            break
        size *= cap_mm / height
    return size


def reference_geometry(char: str, cap_mm: float) -> shapely.Geometry:
    """FreeType outlines combined with the same even-odd rule this repo uses.

    matplotlib's Path.contains_points cannot be used for the comparison: on
    these outlines it fills the counter of 'O' (mask area 3213 at size 100,
    where the true ring is 1980 and the full disc 3277). So the reference is
    taken as outlines only, and the fill rule - which is our own documented
    decision - is applied identically to both sides. Counter-less glyphs are
    still compared purely by outline, and ink areas are reported alongside.
    """
    rings = [
        Polygon(ring) for ring in reference_glyph(char, calibrate_size(cap_mm)).to_polygons()
    ]
    rings = [ring for ring in rings if len(ring.exterior.coords) >= 3]
    if not rings:
        return Polygon()
    result: shapely.Geometry = rings[0]
    for ring in rings[1:]:
        result = result.symmetric_difference(ring)
    return result


def rasterise(geometry: shapely.Geometry, bounds: tuple[float, float, float, float]) -> np.ndarray:
    min_x, min_y, max_x, max_y = bounds
    grid_x, grid_y = np.meshgrid(
        np.linspace(min_x, max_x, GRID), np.linspace(min_y, max_y, GRID)
    )
    points = np.column_stack([grid_x.ravel(), grid_y.ravel()])
    return shapely.contains_xy(geometry, points[:, 0], points[:, 1]).reshape(grid_x.shape)


def iou(left: np.ndarray, right: np.ndarray) -> float:
    union = np.count_nonzero(left | right)
    return float(np.count_nonzero(left & right) / union) if union else 0.0


def compare_glyph(char: str, cap_mm: float, font: GlyphFont) -> dict[str, float]:
    mine = font.glyph(char, cap_mm)
    reference = reference_geometry(char, cap_mm)
    if mine.is_empty or reference.is_empty:
        return {"iou": 0.0, "micro": 0.0, "macro": 0.0, "area_ratio": 0.0}

    min_x, min_y, max_x, max_y = mine.bounds
    ref_min_x, ref_min_y, ref_max_x, ref_max_y = reference.bounds
    min_x, min_y = min(min_x, ref_min_x), min(min_y, ref_min_y)
    max_x, max_y = max(max_x, ref_max_x), max(max_y, ref_max_y)
    pad = 0.04 * max(max_x - min_x, max_y - min_y)
    bounds = (min_x - pad, min_y - pad, max_x + pad, max_y + pad)

    centre = ((min_x + max_x) / 2, (min_y + max_y) / 2)
    mirrored = shapely.affinity.scale(mine, xfact=-1, yfact=1, origin=centre)
    flipped = shapely.affinity.scale(mine, xfact=1, yfact=-1, origin=centre)

    reference_mask = rasterise(reference, bounds)
    return {
        "iou": iou(reference_mask, rasterise(mine, bounds)),
        "micro": iou(reference_mask, rasterise(mirrored, bounds)),
        "macro": iou(reference_mask, rasterise(flipped, bounds)),
        "area_ratio": mine.area / reference.area,
    }


def check_glyphs(font: GlyphFont, cap_mm: float) -> bool:
    """Assert shape/scale/fill-rule, and orientation only where the glyph allows it.

    A near-symmetric glyph (O, o, E) scores high for the mirrored control too,
    so it simply cannot discriminate orientation. Those glyphs only carry the
    shape assertion; the asymmetric ones must beat the control outright.
    """
    print(f"check 1: glyph geometry vs independent FreeType reference (cap={cap_mm} mm)")
    ok = True
    discriminators = 0
    for char in TEST_CHARS:
        result = compare_glyph(char, cap_mm, font)
        control = max(result["micro"], result["macro"])
        informative = control < CONTROL_IS_UNINFORMATIVE
        discriminators += int(informative)
        passed = (
            result["iou"] >= 0.90
            and 0.98 <= result["area_ratio"] <= 1.02
            and (not informative or result["iou"] > control)
        )
        ok &= passed
        note = "" if informative else "  (near-symmetric: control cannot discriminate)"
        print(
            f"  [{'PASS' if passed else 'FAIL'}] {char!r}  IoU={result['iou']:.3f}  "
            f"area x{result['area_ratio']:.4f}  best control={control:.3f}{note}"
        )
    print(f"  -> {discriminators}/{len(TEST_CHARS)} glyphs actually discriminate orientation")
    return bool(ok and discriminators >= 3)


# --------------------------------------------------------------------------- 2


def check_material_removal(font: GlyphFont) -> bool:
    print("\ncheck 2: engraving removes exactly the expected material")
    ok = True
    category = CATEGORIES[0]
    for label, part, builder in (
        ("pedestal", Pedestal(), build_pedestal),
        ("plaque", Plaque(), build_plaque),
    ):
        solid_volume = part.length * part.thickness * part.height
        slot_volume = (
            part.socket_width * part.socket_depth * part.socket_recess
            if isinstance(part, Pedestal)
            else 0.0
        )
        lines = stack_lines(font, category, part, max_width=2 * part.text_area_half_width)
        ink_area = sum(line.geometry.area for line in lines)
        cavity = pedestal_cavity(part) if isinstance(part, Pedestal) else None
        cavity_volume = cavity.volume if cavity is not None else 0.0
        expected = (
            solid_volume - slot_volume - cavity_volume - ink_area * part.layout.engrave_depth
        )

        try:
            mesh = builder(font, category, part)
        except SystemExit as error:
            print(f"  [FAIL] {label:9s} {error}")
            ok = False
            continue

        delta = mesh.volume - expected
        good = abs(delta) < max(0.5, 1e-3 * expected) and mesh.is_watertight
        ok &= good
        print(
            f"  [{'PASS' if good else 'FAIL'}] {label:9s} expected={expected / 1000:.3f} cm3  "
            f"mesh={mesh.volume / 1000:.3f} cm3  delta={delta:.2f} mm3  "
            f"ink={ink_area:.1f} mm2  cavity={cavity_volume / 1000:.2f} cm3  "
            f"watertight={mesh.is_watertight}"
        )
    return bool(ok)


# --------------------------------------------------------------------------- 3


def achieved_cap(font: GlyphFont, text: str, cap_mm: float, available: float) -> tuple[float, float]:
    """Capital height actually rendered after fitting the line to the width."""
    bounds = font.line(text, cap_mm, max_width=None).bounds
    natural_width = bounds[2] - bounds[0]
    scale = min(1.0, available / natural_width) if natural_width > 0 else 1.0
    return cap_mm * scale, natural_width * scale


def check_layout(font: GlyphFont) -> bool:
    print("\ncheck 3: layout fits, stays legible, and keeps its reading order")
    ok = True
    for category in CATEGORIES:
        for label, part in (("pedestal", Pedestal()), ("plaque", Plaque())):
            available = 2 * part.text_area_half_width
            caps: dict[str, float] = {}
            for text, requested in part.layout.caps(category):
                cap, width = achieved_cap(font, text, requested, available)
                caps[text] = cap
                fits = width <= available + 1e-6
                legible = cap >= MIN_CAP_MM
                comfortable = cap >= COMFORT_CAP_MM
                ok &= fits and legible
                flag = "PASS" if fits and legible else "FAIL"
                warn = "" if comfortable else "  <- thin strokes, slice with care"
                print(
                    f"  [{flag}] {category.slug:18s} {label:8s} {text!r:26s} "
                    f"w={width:5.1f}/{available:.1f}  cap={cap:.2f}/{requested:.1f}{warn}"
                )

            order = [
                caps[category.title],
                caps[category.subtitle],
                *(caps[text] for text in category.body),
            ]
            ordered = all(a >= b - 1e-9 for a, b in zip(order, order[1:]))
            ok &= ordered

            lines = stack_lines(font, category, part, max_width=available)
            z_low, z_high = part.z_range
            top = max(line.z_span[1] for line in lines)
            bottom = min(line.z_span[0] for line in lines)
            top_margin, bottom_margin = z_high - top, bottom - z_low
            spaced = min(top_margin, bottom_margin) >= MIN_EDGE_MARGIN_MM
            ok &= spaced
            print(
                f"  [{'PASS' if ordered and spaced else 'FAIL'}] {category.slug:18s} {label:8s} "
                f"order_ok={ordered}  block={bottom:.1f}..{top:.1f} in "
                f"{z_low:.1f}..{z_high:.1f}  margins={bottom_margin:.1f}/{top_margin:.1f} mm"
            )
    return bool(ok)


def check_hollow(font: GlyphFont) -> bool:
    """The hollowing must leave printable walls and a sound slot floor."""
    print("\ncheck 4: hollowing leaves enough material where it matters")
    spec = Pedestal()
    cavity = pedestal_cavity(spec)
    if cavity is None:
        print("  [SKIP] pedestal is solid")
        return True

    solid = spec.length * spec.depth * spec.height
    saved = cavity.volume / solid
    clearance = spec.socket_floor_z - spec.hollow_roof_z
    wall = (spec.length - (cavity.bounds[1][0] - cavity.bounds[0][0])) / 2

    checks = {
        "wall thickness matches the spec": wall >= spec.hollow_wall_mm - 1e-6,
        "socket floor clearance >= 3 mm": clearance >= 3.0 - 1e-6,
        "cavity reaches the bottom face (not sealed)": cavity.bounds[0][2] <= 0.0,
        "cavity clears the socket": cavity.bounds[1][2] <= spec.socket_floor_z - 3.0 + 1e-6,
    }
    ok = all(checks.values())
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print(
        f"  hollowing removes {saved * 100:.0f}% of the model volume "
        f"({cavity.volume / 1000:.1f} cm3 cavity, wall {wall:.1f} mm, "
        f"clearance {clearance:.1f} mm)"
    )
    print(
        "  NOTE: model volume is not print cost. See the filament estimate in\n"
        "        build_premios.py output before claiming this saves material."
    )
    return bool(ok)


def main() -> int:
    font = GlyphFont(FONT_PATH)
    results = [
        check_glyphs(font, 6.0),
        check_material_removal(font),
        check_layout(font),
        check_hollow(font),
    ]
    passed = all(results)
    print(f"\nresult: {'all checks passed' if passed else 'CHECKS FAILED'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
