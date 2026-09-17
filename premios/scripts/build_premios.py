#!/usr/bin/env python3
"""Generate ConRol award geometry.

Produces, for every configured category:
  * a pedestal with the category text engraved on its front face and a slot on
    top for a flat (silhouette) figure, and
  * a standalone engraved plaque that can be glued onto a base.

All geometry is built from text outlines (fontTools -> svgelements -> shapely)
and extruded/boolean-subtracted with trimesh. Every STL is validated before it
is written: watertight, positive volume, sane bounding box.

Usage:  .venv/bin/python scripts/build_premios.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import shapely
import svgelements
import trimesh
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from shapely.affinity import translate
from shapely.geometry import MultiPolygon, Polygon

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "out"

FONT_PATH = Path("/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf")

# Densities in millimetres.
CURVE_STEP_MM = 0.08
SIMPLIFY_MM = 0.015
# Extra stock so the engraving boolean cuts cleanly through the surface.
BOOL_OVERSHOOT_MM = 0.6


@dataclass(frozen=True)
class Pedestal:
    """Box pedestal, drawn in millimetres, sitting on Z=0 and centred on X/Y."""

    length: float = 72.0  # X
    depth: float = 32.0  # Y
    height: float = 16.0  # Z
    slot_length: float = 46.0
    slot_width: float = 2.6
    slot_depth: float = 7.0
    engrave_depth: float = 0.7
    side_margin: float = 4.5
    title_cap_mm: float = 4.2
    subtitle_cap_mm: float = 3.2
    title_z: float = 10.35
    subtitle_z: float = 5.15

    @property
    def text_area_half_width(self) -> float:
        return self.length / 2 - self.side_margin

    @property
    def z_range(self) -> tuple[float, float]:
        return 0.0, self.height


@dataclass(frozen=True)
class Plaque:
    """Standalone flat plaque, lying in the XZ plane, thickness along Y."""

    length: float = 70.0
    height: float = 16.0
    thickness: float = 2.5
    engrave_depth: float = 0.7
    side_margin: float = 4.0
    title_cap_mm: float = 4.2
    subtitle_cap_mm: float = 3.2
    title_z: float = 1.95
    subtitle_z: float = -2.45

    @property
    def text_area_half_width(self) -> float:
        return self.length / 2 - self.side_margin

    @property
    def z_range(self) -> tuple[float, float]:
        return -self.height / 2, self.height / 2


@dataclass(frozen=True)
class Category:
    slug: str
    title: str
    subtitle: str
    extra_lines: list[str] = field(default_factory=list)


CATEGORIES: list[Category] = [
    Category(slug="millor-narrativa", title="MEJOR NARRATIVA", subtitle="ConRol 2025"),
    Category(slug="millor-interpretacio", title="MEJOR INTERPRETACIÓN", subtitle="ConRol 2025"),
]


class GlyphFont:
    """Turns a string into a single shapely geometry, centred on the origin."""

    def __init__(self, path: Path) -> None:
        self._font = TTFont(str(path))
        self._glyphs = self._font.getGlyphSet()
        self._cmap = self._font.getBestCmap()
        self.units_per_em = float(self._font["head"].unitsPerEm)
        self.cap_height = self._measure_cap_height()

    def _measure_cap_height(self) -> float:
        """Ink height of 'H' in font units.

        The OS/2 sCapHeight field cannot be trusted: Liberation Sans Narrow
        Bold declares 1440 units while its 'H' actually measures 1409, which
        would silently render every engraved glyph 2.1% smaller than asked.
        """
        paths = self._subpaths("H")
        if not paths:
            declared = getattr(self._font["OS/2"], "sCapHeight", 0)
            return float(declared or 0.703 * self.units_per_em)
        boxes = [path.bbox() for path in paths]
        return max(box[3] for box in boxes) - min(box[1] for box in boxes)

    def scale_for_cap(self, cap_mm: float) -> float:
        """Millimetres of em size that yield the requested capital height."""
        return cap_mm / self.cap_height

    def _advance(self, char: str) -> float:
        name = self._cmap.get(ord(char))
        return self._glyphs[name].width if name else self.units_per_em * 0.28

    def _subpaths(self, char: str) -> list[svgelements.Path]:
        name = self._cmap.get(ord(char))
        if name is None:
            return []  # whitespace or unmapped character
        pen = SVGPathPen(self._glyphs)
        self._glyphs[name].draw(pen)
        return [svgelements.Path(sub) for sub in svgelements.Path(pen.getCommands()).as_subpaths()]

    def glyph(self, char: str, cap_mm: float) -> shapely.Geometry:
        """One glyph outline in millimetres, with its pen origin at (0, 0)."""
        placed = [(path, 0.0) for path in self._subpaths(char)]
        return _paths_to_geometry(placed, self.scale_for_cap(cap_mm))

    def line(self, text: str, cap_mm: float, max_width: float | None = None) -> shapely.Geometry:
        """Build one text line as an even-odd filled geometry, centred on (0, 0)."""
        scale = self.scale_for_cap(cap_mm)
        if max_width is not None:
            width = sum(self._advance(c) for c in text) * scale
            if width > max_width:
                scale *= max_width / width

        # Pen advances are tracked in font units; the scale is applied once, at
        # sampling time, together with each glyph's advance offset.
        placed: list[tuple[svgelements.Path, float]] = []
        pen_x = 0.0
        for char in text:
            placed.extend((path, pen_x) for path in self._subpaths(char))
            pen_x += self._advance(char)

        geometry = _paths_to_geometry(placed, scale)
        return _centre_on_origin(geometry)


def _paths_to_geometry(
    placed: list[tuple[svgelements.Path, float]], scale: float
) -> shapely.Geometry:
    """Rasterise subpaths into polygons, then apply the even-odd fill rule."""
    rings: list[Polygon] = []
    for path, offset in placed:
        length_mm = path.length() * scale
        if length_mm <= 0:
            continue
        steps = max(8, int(length_mm / CURVE_STEP_MM))
        points = [path.point(i / steps) for i in range(steps + 1)]
        ring = Polygon([((p.x + offset) * scale, p.y * scale) for p in points])
        if not ring.is_valid:
            ring = ring.buffer(0)
        if not ring.is_empty:
            rings.append(ring.simplify(SIMPLIFY_MM, preserve_topology=True))

    if not rings:
        return Polygon()

    # XOR across every ring is exactly the even-odd fill rule, so counters
    # (the hole in an "O") come out as holes without any nesting bookkeeping.
    result: shapely.Geometry = rings[0]
    for ring in rings[1:]:
        result = result.symmetric_difference(ring)
    return result


def _centre_on_origin(geometry: shapely.Geometry) -> shapely.Geometry:
    if geometry.is_empty:
        return geometry
    min_x, min_y, max_x, max_y = geometry.bounds
    return translate(geometry, -(min_x + max_x) / 2, -(min_y + max_y) / 2)


def _extrude(geometry: shapely.Geometry, height: float) -> trimesh.Trimesh:
    """Extrude a 2D geometry along +Z, starting at Z=0."""
    parts = geometry.geoms if isinstance(geometry, MultiPolygon) else [geometry]
    meshes = [
        trimesh.creation.extrude_polygon(part, height)
        for part in parts
        if isinstance(part, Polygon) and not part.is_empty
    ]
    if not meshes:
        raise ValueError("nothing to extrude")
    return trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]


def _face_text_solids(
    font: GlyphFont,
    lines: list[tuple[str, float, float]],
    max_width: float,
    face_y: float,
    engrave_depth: float,
) -> list[trimesh.Trimesh]:
    """Build the cutting solids for text engraved on a face with normal -Y."""
    solids: list[trimesh.Trimesh] = []
    for text, cap_mm, centre_z in lines:
        geometry = font.line(text, cap_mm, max_width=max_width)
        if geometry.is_empty:
            continue
        # Extrude along +Z, then rotate +90 deg about X: (x, y, z) -> (x, -z, y).
        # The 2D Y axis becomes the world Z axis, and the extrusion axis becomes Y.
        solid = _extrude(geometry, engrave_depth + BOOL_OVERSHOOT_MM)
        solid.apply_transform(trimesh.transformations.rotation_matrix(1.5707963, [1, 0, 0]))
        solid.apply_translation([0.0, face_y + engrave_depth, centre_z])
        solids.append(solid)
    return solids


def _inscription(spec: Pedestal | Plaque, category: Category) -> list[tuple[str, float, float]]:
    return [
        (category.title, spec.title_cap_mm, spec.title_z),
        (category.subtitle, spec.subtitle_cap_mm, spec.subtitle_z),
    ]


def _assert_inside(
    solids: list[trimesh.Trimesh], spec: Pedestal | Plaque, label: str
) -> None:
    """A cutting solid that escapes the part silently removes nothing.

    This is not hypothetical: the first version of the plaque placed its
    subtitle at z=11.6 on a plate spanning z=-9..9, so a quarter of the
    engraving was cut in thin air and the mesh volume gave it away.
    """
    z_low, z_high = spec.z_range
    half_x = spec.length / 2
    for solid in solids:
        (min_x, _, min_z), (max_x, _, max_z) = solid.bounds
        if min_x < -half_x - 1e-6 or max_x > half_x + 1e-6:
            raise SystemExit(
                f"{label}: text escapes in X ({min_x:.1f}..{max_x:.1f} vs +-{half_x:.1f})"
            )
        if min_z < z_low - 1e-6 or max_z > z_high + 1e-6:
            raise SystemExit(
                f"{label}: text escapes in Z ({min_z:.1f}..{max_z:.1f} vs {z_low:.1f}..{z_high:.1f})"
            )


def build_pedestal(font: GlyphFont, category: Category, spec: Pedestal) -> trimesh.Trimesh:
    base = trimesh.creation.box(extents=[spec.length, spec.depth, spec.height])
    base.apply_translation([0.0, 0.0, spec.height / 2])

    slot = trimesh.creation.box(
        extents=[spec.slot_length, spec.slot_width, spec.slot_depth + 1.0]
    )
    slot.apply_translation([0.0, 0.0, spec.height - spec.slot_depth + (spec.slot_depth + 1.0) / 2])

    texts = _engraved_text(font, category, spec, face_y=-spec.depth / 2)
    return trimesh.boolean.difference([base, slot, *texts], engine="manifold")


def build_plaque(font: GlyphFont, category: Category, spec: Plaque) -> trimesh.Trimesh:
    plate = trimesh.creation.box(extents=[spec.length, spec.thickness, spec.height])
    texts = _engraved_text(font, category, spec, face_y=-spec.thickness / 2)
    return trimesh.boolean.difference([plate, *texts], engine="manifold")


def _engraved_text(
    font: GlyphFont, category: Category, spec: Pedestal | Plaque, face_y: float
) -> list[trimesh.Trimesh]:
    solids = _face_text_solids(
        font,
        _inscription(spec, category),
        max_width=2 * spec.text_area_half_width,
        face_y=face_y,
        engrave_depth=spec.engrave_depth,
    )
    _assert_inside(solids, spec, category.slug)
    return solids


def validate(mesh: trimesh.Trimesh, label: str) -> None:
    """Fail loudly rather than shipping an unprintable STL."""
    problems: list[str] = []
    if not mesh.is_watertight:
        problems.append("mesh is NOT watertight")
    if mesh.volume <= 0:
        problems.append(f"non-positive volume ({mesh.volume:.1f} mm3)")
    if not mesh.is_winding_consistent:
        problems.append("inconsistent winding")
    extents = mesh.extents
    if min(extents) <= 0:
        problems.append(f"degenerate extents {extents}")
    status = "OK" if not problems else "FAIL"
    print(
        f"  [{status}] {label}: watertight={mesh.is_watertight} "
        f"volume={mesh.volume / 1000:.2f} cm3 "
        f"bbox={extents[0]:.1f}x{extents[1]:.1f}x{extents[2]:.1f} mm "
        f"faces={len(mesh.faces)}"
    )
    for problem in problems:
        print(f"         ! {problem}")
    if problems:
        raise SystemExit(f"validation failed for {label}")


def main() -> int:
    if not FONT_PATH.exists():
        raise SystemExit(f"font not found: {FONT_PATH}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    font = GlyphFont(FONT_PATH)
    pedestal_spec = Pedestal()
    plaque_spec = Plaque()

    for category in CATEGORIES:
        print(f"category: {category.slug}")
        pedestal = build_pedestal(font, category, pedestal_spec)
        validate(pedestal, f"peana-{category.slug}.stl")
        pedestal.export(OUT_DIR / f"peana-{category.slug}.stl")

        plaque = build_plaque(font, category, plaque_spec)
        validate(plaque, f"placa-{category.slug}.stl")
        plaque.export(OUT_DIR / f"placa-{category.slug}.stl")

    print(f"\nwritten to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
