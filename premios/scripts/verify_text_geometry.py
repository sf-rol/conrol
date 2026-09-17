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
   solid may escape the part. An escaping cut is silent in the mesh, which is
   exactly how the first plaque draft shipped with 26% of its engraving in the
   air, so it is asserted explicitly.

3. Layout: engraved width within the available width, capital height above the
   legibility floor, and the title never rendered smaller than the subtitle.

Usage:  .venv/bin/python scripts/verify_text_geometry.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Polygon
import shapely.affinity
from matplotlib.font_manager import FontProperties

from matplotlib.textpath import TextPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_premios import (  # noqa: E402
    CATEGORIES,
    FONT_PATH,
    Category,
    GlyphFont,
    Pedestal,
    Plaque,
    _inscription,
    build_pedestal,
    build_plaque,
)

GRID = 260
MIN_CAP_MM = 2.5  # legibility floor for a 0.4 mm nozzle
TEST_CHARS = "MEORAÓ2o5"
REFERENCE_CAP_EM = 0.688  # starting guess for cap height / em
CONTROL_IS_UNINFORMATIVE = 0.90
FONT_PROP = FontProperties(fname=str(FONT_PATH))


# --------------------------------------------------------------------------- 1


def reference_glyph(char: str, size: float) -> TextPath:
    """Independent glyph outline via matplotlib/FreeType, pen origin at (0, 0)."""
    return TextPath((0, 0), char, size=size, prop=FONT_PROP)


def reference_geometry(char: str, cap_mm: float) -> shapely.Geometry:
    """FreeType outlines combined with the same even-odd rule this repo uses.

    matplotlib's Path.contains_points cannot be used for the comparison: on
    these outlines it fills the counter of 'O' (mask area 3213 at size 100,
    where the true ring is 1980 and the full disc 3277). So the reference is
    taken as outlines only, and the fill rule - which is our own documented
    decision - is applied identically to both sides. Counter-less glyphs are
    still compared purely by outline, and ink areas are reported alongside.
    """
    path = reference_glyph(char, calibrate_size(cap_mm))
    rings = [Polygon(ring) for ring in path.to_polygons() if len(ring) >= 3]
    if not rings:
        return Polygon()
    result: shapely.Geometry = rings[0]
    for ring in rings[1:]:
        result = result.symmetric_difference(ring)
    return result


def calibrate_size(cap_mm: float) -> float:
    """Em size in TextPath units that yields the requested capital height."""
    size = cap_mm / REFERENCE_CAP_EM
    for _ in range(3):
        height = reference_glyph("H", size).get_extents().height
        if height <= 0:
            break
        size *= cap_mm / height
    return size


def rasterise(geometry, bounds: tuple[float, float, float, float]) -> np.ndarray:
    min_x, min_y, max_x, max_y = bounds
    grid_x, grid_y = np.meshgrid(
        np.linspace(min_x, max_x, GRID), np.linspace(min_y, max_y, GRID)
    )
    points = np.column_stack([grid_x.ravel(), grid_y.ravel()])
    mask = shapely.contains_xy(geometry, points[:, 0], points[:, 1])
    return mask.reshape(grid_x.shape)


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


def part_thickness(spec: Pedestal | Plaque) -> float:
    return spec.depth if isinstance(spec, Pedestal) else spec.thickness


def check_material_removal(font: GlyphFont) -> bool:
    print("\ncheck 2: engraving removes exactly the expected material")
    ok = True
    for label, spec, builder in (
        ("pedestal", Pedestal(), build_pedestal),
        ("plaque", Plaque(), build_plaque),
    ):
        solid_volume = spec.length * part_thickness(spec) * spec.height
        slot_volume = (
            spec.slot_length * spec.slot_width * spec.slot_depth
            if isinstance(spec, Pedestal)
            else 0.0
        )
        lines = _inscription(spec, CATEGORIES[0])
        ink_area = sum(
            font.line(text, cap, max_width=2 * spec.text_area_half_width).area
            for text, cap, _ in lines
        )
        expected = solid_volume - slot_volume - ink_area * spec.engrave_depth

        try:
            mesh = builder(font, CATEGORIES[0], spec)
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
            f"ink={ink_area:.1f} mm2  watertight={mesh.is_watertight}"
        )
    return bool(ok)


# --------------------------------------------------------------------------- 3


def check_layout(font: GlyphFont) -> bool:
    print("\ncheck 3: layout fits the part, stays legible, title outranks subtitle")
    ok = True
    for category in CATEGORIES:
        for label, spec in (("pedestal", Pedestal()), ("plaque", Plaque())):
            available = 2 * spec.text_area_half_width
            caps: dict[str, float] = {}
            for text, cap, _ in _inscription(spec, category):
                natural = font.line(text, cap, max_width=None).bounds
                natural_width = natural[2] - natural[0]
                achieved_cap = cap * min(1.0, available / natural_width)
                fitted = font.line(text, cap, max_width=available).bounds
                width = fitted[2] - fitted[0]
                caps[text] = achieved_cap
                fits = width <= available + 1e-6
                legible = achieved_cap >= MIN_CAP_MM
                ok &= fits and legible
                print(
                    f"  [{'PASS' if fits and legible else 'FAIL'}] {label:8s} {text!r:24s} "
                    f"width={width:5.1f}/{available:.1f} mm  "
                    f"cap={achieved_cap:.2f} mm (asked {cap:.1f})"
                )
            title_cap = caps[category.title]
            subtitle_cap = caps[category.subtitle]
            ordered = title_cap >= subtitle_cap
            ok &= ordered
            print(
                f"  [{'PASS' if ordered else 'FAIL'}] {label:8s} title {title_cap:.2f} mm "
                f"vs subtitle {subtitle_cap:.2f} mm"
            )
    return bool(ok)


def main() -> int:
    font = GlyphFont(FONT_PATH)
    results = [
        check_glyphs(font, 6.0),
        check_material_removal(font),
        check_layout(font),
    ]
    passed = all(results)
    print(f"\nresult: {'all checks passed' if passed else 'CHECKS FAILED'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
