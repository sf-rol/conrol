#!/usr/bin/env python3
"""Generate ConRol award geometry.

Produces, for every configured category:
  * a pedestal with the award text engraved on its front face and a slot on top
    for a flat (silhouette) figure, and
  * a standalone engraved plaque that can be glued onto a base instead.

All geometry is built from real font outlines (fontTools -> svgelements ->
shapely) and extruded/boolean-subtracted with trimesh. Every STL is validated
before it is written: watertight, single shell, positive volume, sane bounds,
and engraved text that actually stays inside the part.

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
class TextLayout:
    """How the engraved lines are sized and stacked, in millimetres."""

    title_cap_mm: float = 4.2
    subtitle_cap_mm: float = 3.0
    body_cap_mm: float = 2.8
    line_gap_mm: float = 1.2
    side_margin_mm: float = 3.5
    engrave_depth: float = 0.7

    def caps(self, category: Category) -> list[tuple[str, float]]:
        """Ordered (text, capital height) pairs, biggest line first."""
        lines = [(category.title, self.title_cap_mm), (category.subtitle, self.subtitle_cap_mm)]
        lines.extend((text, self.body_cap_mm) for text in category.body)
        return lines


@dataclass(frozen=True)
class Pedestal:
    """Box pedestal, in millimetres, sitting on Z=0 and centred on X/Y."""

    length: float = 72.0  # X
    depth: float = 34.0  # Y
    height: float = 26.0  # Z
    slot_length: float = 46.0
    slot_width: float = 2.6
    slot_depth: float = 8.0
    layout: TextLayout = field(default_factory=TextLayout)
    hollow: bool = True
    hollow_wall_mm: float = 2.4
    hollow_roof_rise_mm: float = 3.0
    hollow_roof_clearance_mm: float = 3.0

    @property
    def thickness(self) -> float:
        return self.depth

    @property
    def hollow_roof_z(self) -> float:
        """Top of the cavity.

        Kept at least `hollow_roof_clearance_mm` below the figure slot: the
        floor of that slot is thin, and at 1 mm of clearance a figure that
        wobbles in the pocket cracks straight through it.
        """
        return self.height - self.slot_depth - self.hollow_roof_clearance_mm

    @property
    def slot_floor_z(self) -> float:
        return self.height - self.slot_depth

    @property
    def text_area_half_width(self) -> float:
        return self.length / 2 - self.layout.side_margin_mm

    @property
    def z_range(self) -> tuple[float, float]:
        return 0.0, self.height

    @property
    def text_block_center_z(self) -> float:
        return self.height / 2


@dataclass(frozen=True)
class Plaque:
    """Standalone flat plaque, in the XZ plane, thickness along Y."""

    length: float = 68.0
    height: float = 22.0
    thickness: float = 2.5
    layout: TextLayout = field(default_factory=TextLayout)

    @property
    def text_area_half_width(self) -> float:
        return self.length / 2 - self.layout.side_margin_mm

    @property
    def z_range(self) -> tuple[float, float]:
        return -self.height / 2, self.height / 2

    @property
    def text_block_center_z(self) -> float:
        return 0.0


@dataclass(frozen=True)
class Category:
    """One award. `body` lines are already wrapped: the plate does not word-wrap."""

    slug: str
    title: str
    subtitle: str
    body: tuple[str, ...] = ()


CATEGORIES: list[Category] = [
    Category(
        slug="aportacio",
        title="ConRol 2026",
        subtitle="POR APORTAR UNA ACTIVIDAD",
        body=("GRACIAS POR REMOVER", "EL CALDERO"),
    ),
    Category(
        slug="dramaqeen",
        title="DRAMAQEEN",
        subtitle="ConRol 2026",
        body=("POR BUSCAR EL DRAMA", "INFINITO E INTENSO"),
    ),
    Category(
        slug="abuelo-cebolleta",
        title="ABUELO/A CEBOLLETA",
        subtitle="ConRol 2026",
        body=("PORQUE EN MIS TIEMPOS", "ESTO MOLABA MÁS"),
    ),
    Category(
        slug="intensito",
        title="INTENSITO",
        subtitle="ConRol 2026",
        body=("POR TOMÁRSELO TODO", "MUY EN SERIO"),
    ),
    Category(
        slug="neurotipico",
        title="NEUROTÍPICO",
        subtitle="ConRol 2026",
        body=("POR SER EL NORMALITO", "DE LA MESA"),
    ),
    Category(
        slug="molusco-bivalvo",
        title="MOLUSCO BIVALVO",
        subtitle="ConRol 2026",
        body=("POR SENTIRLO TODO", "POR DENTRO"),
    ),
    Category(
        slug="troll-cavernas",
        title="TROLL DE LAS CAVERNAS",
        subtitle="ConRol 2026",
        body=("POR RONCAR COMO UN", "MONSTRUO ÉPICO"),
    ),
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

        return _centre_on_origin(_paths_to_geometry(placed, scale))


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


@dataclass(frozen=True)
class PlacedLine:
    """One engraved line, with the Z of its ink bounding-box centre."""

    text: str
    geometry: shapely.Geometry
    center_z: float
    height: float

    @property
    def z_span(self) -> tuple[float, float]:
        return self.center_z - self.height / 2, self.center_z + self.height / 2


def stack_lines(
    font: GlyphFont, category: Category, part: Pedestal | Plaque, max_width: float
) -> list[PlacedLine]:
    """Lay the lines out as one vertically centred block.

    Lines are stacked by their real ink bounding box, not by their capital
    height, so accents and descenders cannot collide with the line above.
    """
    built: list[tuple[str, shapely.Geometry, float]] = []
    for text, cap_mm in part.layout.caps(category):
        if not text.strip():
            continue  # a plain part has no inscription at all
        geometry = font.line(text, cap_mm, max_width=max_width)
        if geometry.is_empty:
            continue
        built.append((text, geometry, geometry.bounds[3] - geometry.bounds[1]))
    if not built:
        return []

    gap = part.layout.line_gap_mm
    total = sum(height for _, _, height in built) + gap * (len(built) - 1)
    cursor = part.text_block_center_z + total / 2

    placed: list[PlacedLine] = []
    for text, geometry, height in built:
        placed.append(PlacedLine(text, geometry, cursor - height / 2, height))
        cursor -= height + gap
    return placed


def _face_text_solids(
    lines: list[PlacedLine], face_y: float, engrave_depth: float
) -> list[trimesh.Trimesh]:
    """Build the cutting solids for text engraved on a face with normal -Y."""
    solids: list[trimesh.Trimesh] = []
    for line in lines:
        # Extrude along +Z, then rotate +90 deg about X: (x, y, z) -> (x, -z, y).
        # The 2D Y axis becomes the world Z axis, and the extrusion axis becomes Y.
        solid = _extrude(line.geometry, engrave_depth + BOOL_OVERSHOOT_MM)
        solid.apply_transform(trimesh.transformations.rotation_matrix(1.5707963, [1, 0, 0]))
        solid.apply_translation([0.0, face_y + engrave_depth, line.center_z])
        solids.append(solid)
    return solids


def _assert_inside(
    solids: list[trimesh.Trimesh], part: Pedestal | Plaque, label: str
) -> None:
    """A cutting solid that escapes the part silently removes nothing.

    This is not hypothetical: the first version of the plaque placed its
    subtitle at z=11.6 on a plate spanning z=-9..9, so a quarter of the
    engraving was cut in thin air and the mesh volume gave it away.
    """
    z_low, z_high = part.z_range
    half_x = part.length / 2
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


def _engraved_text(
    font: GlyphFont, category: Category, part: Pedestal | Plaque, face_y: float
) -> list[trimesh.Trimesh]:
    lines = stack_lines(font, category, part, max_width=2 * part.text_area_half_width)
    solids = _face_text_solids(lines, face_y=face_y, engrave_depth=part.layout.engrave_depth)
    _assert_inside(solids, part, category.slug)
    return solids


def _rectangular_frustum(
    bottom: tuple[float, float], top: tuple[float, float], height: float
) -> trimesh.Trimesh:
    """Rectangular frustum from Z=0 to Z=height, centred on X/Y."""
    bottom_x, bottom_y = bottom[0] / 2, bottom[1] / 2
    top_x, top_y = top[0] / 2, top[1] / 2
    vertices = [
        (-bottom_x, -bottom_y, 0.0),
        (bottom_x, -bottom_y, 0.0),
        (bottom_x, bottom_y, 0.0),
        (-bottom_x, bottom_y, 0.0),
        (-top_x, -top_y, height),
        (top_x, -top_y, height),
        (top_x, top_y, height),
        (-top_x, top_y, height),
    ]
    faces = [
        [0, 2, 1], [0, 3, 2],  # bottom, facing -Z
        [4, 5, 6], [4, 6, 7],  # top, facing +Z
        [0, 1, 5], [0, 5, 4],
        [1, 2, 6], [1, 6, 5],
        [2, 3, 7], [2, 7, 6],
        [3, 0, 4], [3, 4, 7],
    ]
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.fix_normals()
    return mesh


def pedestal_cavity(spec: Pedestal) -> trimesh.Trimesh | None:
    """Hollow volume removed from underneath the pedestal.

    A 26 mm solid block is 62.6 cm3 of filament, which across a full set of
    awards is tens of hours of printing. Removing it from below leaves
    straighter walls and an open bottom - a sealed internal void is simply not
    printable on an FDM machine - and the cavity is a convenient pocket for
    weighting the award with sand or a bolt. The roof tapers at 45 degrees so
    it prints without supports, and it is kept clear of the figure slot.
    """
    if not spec.hollow:
        return None
    cavity_length = spec.length - 2 * spec.hollow_wall_mm
    cavity_depth = spec.depth - 2 * spec.hollow_wall_mm
    roof_z = spec.hollow_roof_z
    straight_top_z = roof_z - spec.hollow_roof_rise_mm
    if straight_top_z <= 0:
        raise SystemExit("hollow cavity has no room left; reduce the wall thickness")

    wall_height = straight_top_z
    walls = trimesh.creation.box(extents=[cavity_length, cavity_depth, wall_height])
    walls.apply_translation([0.0, 0.0, straight_top_z - wall_height / 2])

    roof = _rectangular_frustum(
        (cavity_length, cavity_depth),
        (
            cavity_length - 2 * spec.hollow_roof_rise_mm,
            cavity_depth - 2 * spec.hollow_roof_rise_mm,
        ),
        spec.hollow_roof_rise_mm,
    )
    roof.apply_translation([0.0, 0.0, straight_top_z])
    return trimesh.boolean.union([walls, roof], engine="manifold")


def _bottom_opener(cavity: trimesh.Trimesh) -> trimesh.Trimesh:
    """Thin prism straddling Z=0 so the boolean opens the bottom cleanly.

    It stays inside the cavity footprint and is centred on the bottom face, so
    it removes nothing that the cavity does not already remove: it only avoids
    a coplanar boolean at Z=0. Keeping it out of `pedestal_cavity` is what lets
    the analytic volume check stay exact.
    """
    (min_x, min_y, _), (max_x, max_y, _) = cavity.bounds
    opener = trimesh.creation.box(
        extents=[max_x - min_x, max_y - min_y, 2 * BOOL_OVERSHOOT_MM]
    )
    opener.apply_translation([(min_x + max_x) / 2, (min_y + max_y) / 2, 0.0])
    return opener


def build_pedestal(font: GlyphFont, category: Category, spec: Pedestal) -> trimesh.Trimesh:
    base = trimesh.creation.box(extents=[spec.length, spec.depth, spec.height])
    base.apply_translation([0.0, 0.0, spec.height / 2])

    slot = trimesh.creation.box(
        extents=[spec.slot_length, spec.slot_width, spec.slot_depth + 1.0]
    )
    slot.apply_translation(
        [0.0, 0.0, spec.height - spec.slot_depth + (spec.slot_depth + 1.0) / 2]
    )

    texts = _engraved_text(font, category, spec, face_y=-spec.depth / 2)
    cavity = pedestal_cavity(spec)
    cutters = [slot, *texts]
    if cavity is not None:
        cutters.extend([cavity, _bottom_opener(cavity)])
    return trimesh.boolean.difference([base, *cutters], engine="manifold")


def build_plaque(font: GlyphFont, category: Category, spec: Plaque) -> trimesh.Trimesh:
    plate = trimesh.creation.box(extents=[spec.length, spec.thickness, spec.height])
    texts = _engraved_text(font, category, spec, face_y=-spec.thickness / 2)
    return trimesh.boolean.difference([plate, *texts], engine="manifold")


def validate(mesh: trimesh.Trimesh, label: str) -> None:
    """Fail loudly rather than shipping an unprintable STL."""
    problems: list[str] = []
    if not mesh.is_watertight:
        problems.append("mesh is NOT watertight")
    if mesh.volume <= 0:
        problems.append(f"non-positive volume ({mesh.volume:.1f} mm3)")
    if not mesh.is_winding_consistent:
        problems.append("inconsistent winding")
    if min(mesh.extents) <= 0:
        problems.append(f"degenerate extents {mesh.extents}")
    status = "OK" if not problems else "FAIL"
    print(
        f"  [{status}] {label}: watertight={mesh.is_watertight} "
        f"volume={mesh.volume / 1000:.2f} cm3 "
        f"bbox={mesh.extents[0]:.1f}x{mesh.extents[1]:.1f}x{mesh.extents[2]:.1f} mm "
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

    # One pedestal shared by every award, for the glue-a-plaque-on-it route.
    # Engraving the pedestal *and* gluing a plaque over it would print the text
    # twice, so the two routes need different pedestals.
    print("category: (plain, matches every plaque)")
    plain = build_pedestal(font, Category(slug="lisa", title="", subtitle=""), pedestal_spec)
    validate(plain, "peana-lisa.stl")
    plain.export(OUT_DIR / "peana-lisa.stl")

    print(f"\n{len(CATEGORIES)} categories written to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
