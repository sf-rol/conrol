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
from shapely.geometry import Polygon

from fist_carved import FistCarved, build_fist_carved
from fist_cubist import FistCubist, build_fist_cubist
from fist_elegant import FistElegant, build_fist_elegant
from fist_figure import FistFigure, build_fist
from geometry_common import BOOL_OVERSHOOT_MM, box_at, extrude, rectangular_frustum

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "out"

FONT_PATH = Path("/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf")

# Slicing assumptions used only for the filament estimate, not for the geometry.
INFILL_FRACTION = 0.15
PERIMETER_WIDTH_MM = 1.26

# Densities in millimetres.
CURVE_STEP_MM = 0.08
SIMPLIFY_MM = 0.015

# How the text reaches the award.
#   "plaque"   - one plain pedestal for every award, text on a glued plaque.
#                The plaque can be a contrasting colour, a botched engraving
#                wastes 3.6 cm3 instead of 34, and only one pedestal has to be
#                printed and verified.
#   "engraved" - the text goes straight onto each pedestal. No assembly at all.
# Do not mix the two on the same pedestal: it would print the text twice.
ROUTE = "plaque"

# The text is cut into the sculpture's own base, which is the chosen route: no
# separate plate, so nothing to glue and nothing that can come off. The reference
# sculpture carries its text that way already, and a plate that has to fill the
# face is visually the same thing minus the glue. Set to True to also emit the
# standalone plate, for the glue route.
EMIT_PLATES = False

# Build plate layout for the combined 3MF, in millimetres.
PLATE_COLUMNS = 4
PLATE_PITCH_MM = 55.0


# The top line of every plaque. Fixed, because its only job is to say which
# event this is.
EVENT_LINE = "ConRol 2026"


@dataclass(frozen=True)
class TextLayout:
    """Three lines, in a fixed order: event, award name, short phrase.

    An identifier on top, the award name as the hero, and the joke underneath.
    Only the name is sized to dominate; the other two are deliberately small so
    that three lines fit on a plate barely 10 mm tall.
    """

    event_cap_mm: float
    name_cap_mm: float
    phrase_cap_mm: float
    line_gap_mm: float
    side_margin_mm: float
    engrave_depth: float
    # The block of text must keep this much clear of both edges. Stacking shrinks
    # the capitals until it does, per category, so that an accented line - which
    # rises above the capital height - is the only one that gets smaller instead
    # of dragging every plaque down with it.
    min_margin_mm: float = 1.0

    def caps(self, category: Category) -> list[tuple[str, float]]:
        """Ordered (text, capital height) pairs, top line first."""
        return [
            (EVENT_LINE, self.event_cap_mm),
            (category.name, self.name_cap_mm),
            (category.phrase, self.phrase_cap_mm),
        ]


# Sized for the plaque, which is the tight one: the reference sculpture's base
# gives it a face of 46.1 x 11.1 mm and nothing more.
PLAQUE_LAYOUT = TextLayout(
    event_cap_mm=2.8,
    name_cap_mm=3.4,
    phrase_cap_mm=2.8,
    line_gap_mm=0.35,
    side_margin_mm=1.2,
    engrave_depth=0.6,
)

# The pedestal's face is 68 x 22 mm, so the same three lines can breathe.
PEDESTAL_LAYOUT = TextLayout(
    event_cap_mm=3.2,
    name_cap_mm=4.6,
    phrase_cap_mm=3.2,
    line_gap_mm=1.0,
    side_margin_mm=3.5,
    engrave_depth=0.7,
)


@dataclass(frozen=True)
class Pedestal:
    """Box pedestal, in millimetres, sitting on Z=0 and centred on X/Y.

    The figure sits in a rectangular socket (a mortise) rather than a thin
    slot: a three-dimensional fist needs a footprint it can stand in, and the
    mortise gives the joint shear strength so the figure cannot be knocked off
    sideways. `socket_clearance_mm` is the slop per side that lets the tenon
    actually drop in on a real printer.
    """

    length: float = 72.0  # X
    depth: float = 34.0  # Y
    height: float = 26.0  # Z
    socket_width: float = 30.5
    socket_depth: float = 22.5
    socket_recess: float = 6.0
    layout: TextLayout = field(default_factory=lambda: PEDESTAL_LAYOUT)
    hollow: bool = True
    hollow_wall_mm: float = 1.8
    hollow_roof_rise_mm: float = 3.0
    hollow_roof_clearance_mm: float = 3.0

    @property
    def thickness(self) -> float:
        return self.depth

    @property
    def socket_floor_z(self) -> float:
        return self.height - self.socket_recess

    @property
    def hollow_roof_z(self) -> float:
        """Top of the cavity.

        Kept at least `hollow_roof_clearance_mm` below the socket floor: that
        floor is thin, and a figure that rocks in the mortise would crack
        straight through a thinner one.
        """
        return self.socket_floor_z - self.hollow_roof_clearance_mm

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
    """Standalone plaque, in the XZ plane, thickness along Y.

    Deliberately sized to the reference sculpture's base, whose front face is
    46.1 x 11.1 mm. It is nearly as wide as that face because three legible
    lines need the room; the reference's own plate was only 20.3 x 5.0 mm, and
    no readable text fits that at a 100 mm award.
    """

    length: float = 49.0
    height: float = 12.7
    thickness: float = 2.2
    layout: TextLayout = field(default_factory=lambda: PLAQUE_LAYOUT)

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
    """One award: what it is called, and the few words that land the joke.

    Both are already short. The plate does not word-wrap, so a line that is too
    long gets scaled down rather than broken, and scaling down is what pushes
    text below the legibility floor.
    """

    slug: str
    name: str
    phrase: str


CATEGORIES: list[Category] = [
    Category(slug="aportacio", name="SANCHO PANZA", phrase="SIN TI, NO HAY CONROL"),
    Category(slug="refinament", name="REFINAMIENTO", phrase="DEL GESTO"),
    Category(slug="dramaqeen", name="DRAMAQEEN", phrase="LLORA SIN FRENO"),
    Category(slug="abuelo-cebolleta", name="ABUELO/A CEBOLLETA", phrase="ANTES, TODO ERA MEJOR"),
    Category(slug="intensito", name="INTENSITO", phrase="EVANGELIZA CON PASIÓN"),
    Category(slug="neurotipico", name="NEUROTÍPICO", phrase="ÚNICO EN EL ROL"),
    Category(slug="molusco-bivalvo", name="MOLUSCO BIVALVO", phrase="LO VIVE POR DENTRO"),
    Category(slug="troll-cavernas", name="TROLL CAVERNAS", phrase="TERROR DE LA NOCHE"),
]


@dataclass(frozen=True)
class ReferenceBase:
    """The reference sculpture's own base, engraved directly.

    Measured from `out/figura-referencia-100mm.stl` after the base was enlarged
    to carry three legible lines. Engraving here means no separate plate, so
    nothing to glue and nothing that can come off.
    """

    length: float = 49.19
    height: float = 12.71
    face_y: float = -10.56
    layout: TextLayout = field(default_factory=lambda: PLAQUE_LAYOUT)

    @property
    def text_area_half_width(self) -> float:
        return self.length / 2 - self.layout.side_margin_mm

    @property
    def z_range(self) -> tuple[float, float]:
        return 0.0, self.height

    @property
    def text_block_center_z(self) -> float:
        return self.height / 2


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
        """One text line as an even-odd filled geometry, centred on (0, 0)."""
        return _centre_on_origin(self.line_at_baseline(text, cap_mm, max_width))

    def line_at_baseline(
        self, text: str, cap_mm: float, max_width: float | None = None
    ) -> shapely.Geometry:
        """One text line with the font baseline still on Y=0.

        Kept baseline-referenced because stacking lines by their ink bounding box
        is wrong: a descender - the tail of a Q, a g, a p - would then push every
        line below it downwards. Typesetting stacks by baseline and lets
        descenders hang into the leading, and that is what `stack_lines` needs.
        """
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

        return _paths_to_geometry(placed, scale)

    def line_metrics(
        self, text: str, cap_mm: float, max_width: float | None = None
    ) -> tuple[shapely.Geometry, float, float]:
        """Centred geometry plus how far its ink rises and falls from the baseline."""
        geometry = self.line_at_baseline(text, cap_mm, max_width)
        if geometry.is_empty:
            return geometry, 0.0, 0.0
        _, min_y, _, max_y = geometry.bounds
        return _centre_on_origin(geometry), max_y, -min_y


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
    font: GlyphFont, category: Category, part: Pedestal | Plaque | ReferenceBase, max_width: float
) -> list[PlacedLine]:
    """Lay the lines out as one vertically centred block.

    Lines are stacked by baseline, not by ink bounding box: a descender - the tail
    of a Q, the comma in "SIN TI, NO HAY CONROL" - would otherwise push every line
    below it downwards. Typesetting stacks by baseline and lets descenders hang
    into the leading, which is what keeps the block from inflating.

    The capitals are then shrunk, for this category only, until the block clears
    `min_margin_mm` at both edges. The caps in the layout are therefore a
    maximum, not a promise: an accented line ends up smaller, and the rest stay
    as large as they fit.
    """
    scale = vertical_fit_scale(font, category, part, max_width)
    placed, _ = _stack_at_scale(font, category, part, max_width, scale)
    return placed


def vertical_fit_scale(
    font: GlyphFont,
    category: Category,
    part: Pedestal | Plaque | ReferenceBase,
    max_width: float,
) -> float:
    """How much the capitals have to shrink for this category to fit.

    Exposed so the verification can report the size actually used rather than the
    size requested: an accented line ends up smaller, and every other line keeps
    its full size.
    """
    available = (part.z_range[1] - part.z_range[0]) - 2 * part.layout.min_margin_mm
    scale = 1.0
    for _ in range(8):
        _, total = _stack_at_scale(font, category, part, max_width, scale)
        if total <= 0.0 or total <= available:
            break
        scale *= max(0.5, available / total)
    return scale


def _stack_at_scale(
    font: GlyphFont,
    category: Category,
    part: Pedestal | Plaque | ReferenceBase,
    max_width: float,
    scale: float,
) -> tuple[list[PlacedLine], float]:
    built: list[tuple[str, shapely.Geometry, float, float]] = []
    for text, cap_mm in part.layout.caps(category):
        if not text.strip():
            continue  # a plain part has no inscription at all
        geometry, ascender, descender = font.line_metrics(
            text, cap_mm * scale, max_width=max_width
        )
        if geometry.is_empty:
            continue
        built.append((text, geometry, ascender, descender))
    if not built:
        return [], 0.0

    gap = part.layout.line_gap_mm
    # Baseline-to-baseline spacing. Normally the next line's ascender plus the
    # gap, widened when the line above has a descender that would run into it.
    spacings = [
        ascender + max(gap, descender_above + 0.1)
        for (_, _, _, descender_above), (_, _, ascender, _) in zip(built, built[1:])
    ]
    total = built[0][2] + sum(spacings) + built[-1][3]
    baseline = part.text_block_center_z + total / 2 - built[0][2]

    placed: list[PlacedLine] = []
    for index, (text, geometry, ascender, descender) in enumerate(built):
        if index:
            baseline -= spacings[index - 1]
        height = ascender + descender
        placed.append(PlacedLine(text, geometry, baseline + (ascender - descender) / 2, height))
    return placed, total


def _face_text_solids(
    lines: list[PlacedLine], face_y: float, engrave_depth: float
) -> list[trimesh.Trimesh]:
    """Build the cutting solids for text engraved on a face with normal -Y."""
    solids: list[trimesh.Trimesh] = []
    for line in lines:
        # Extrude along +Z, then rotate +90 deg about X: (x, y, z) -> (x, -z, y).
        # The 2D Y axis becomes the world Z axis, and the extrusion axis becomes Y.
        solid = extrude(line.geometry, engrave_depth + BOOL_OVERSHOOT_MM)
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


def pedestal_cavity(spec: Pedestal) -> trimesh.Trimesh | None:
    """Hollow volume removed from underneath the pedestal.

    Note what this does and does not buy. A 26 mm solid block is 63.6 cm3 of
    *model*, but a slicer printing it at 15% infill would only use about
    20-25 cm3 of filament, so hollowing is not the material saving it looks
    like. What it actually buys is a uniform, predictable wall instead of
    whatever infill the slicer picks, and - the real point - an open pocket you
    can fill with sand. A 100 mm figure on a light base tips over the first
    time someone brushes the table, and ballast is the only thing that fixes
    that. `scripts/build_premios.py` prints the estimated filament both ways.

    The bottom is left open (a sealed internal void is not printable on FDM)
    and the roof tapers at 45 degrees so it needs no supports.
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

    roof = rectangular_frustum(
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

    socket = box_at(
        (spec.socket_width, spec.socket_depth, spec.socket_recess + BOOL_OVERSHOOT_MM),
        (0.0, 0.0, spec.socket_floor_z + (spec.socket_recess + BOOL_OVERSHOOT_MM) / 2),
    )

    texts = _engraved_text(font, category, spec, face_y=-spec.depth / 2)
    cavity = pedestal_cavity(spec)
    cutters = [socket, *texts]
    if cavity is not None:
        cutters.extend([cavity, _bottom_opener(cavity)])
    return trimesh.boolean.difference([base, *cutters], engine="manifold")


def build_plaque(font: GlyphFont, category: Category, spec: Plaque) -> trimesh.Trimesh:
    plate = trimesh.creation.box(extents=[spec.length, spec.thickness, spec.height])
    texts = _engraved_text(font, category, spec, face_y=-spec.thickness / 2)
    return trimesh.boolean.difference([plate, *texts], engine="manifold")


def build_engraved_reference(
    font: GlyphFont, category: Category, blank: trimesh.Trimesh, spec: ReferenceBase
) -> trimesh.Trimesh:
    """The sculpture with its award text cut into its own base."""
    texts = _engraved_text(font, category, spec, face_y=spec.face_y)
    return trimesh.boolean.difference([blank, *texts], engine="manifold")


def write_combined_3mf(meshes: list[tuple[str, trimesh.Trimesh]], target: Path) -> None:
    """One file holding every engraved award, already placed on the plate.

    STL cannot do this: it is a triangle soup with no names, no units and no
    transforms, so eight awards become 78k anonymous triangles in one blob. 3MF
    keeps them as named objects with millimetre units, which is what lets a
    slicer show `premio-troll-cavernas` as a selectable object. Engraving means
    every award is a unique object, so the slicer's "multiply" no longer applies;
    this file is the substitute, laid out so it needs no arranging by hand.
    """
    scene = trimesh.Scene()
    for index, (name, mesh) in enumerate(meshes):
        placed = mesh.copy()
        column = index % PLATE_COLUMNS
        row = index // PLATE_COLUMNS
        placed.apply_translation(
            [
                (column - (PLATE_COLUMNS - 1) / 2.0) * PLATE_PITCH_MM,
                row * PLATE_PITCH_MM * 0.75,
                0.0,
            ]
        )
        scene.add_geometry(placed, node_name=name, geom_name=name)
    target.write_bytes(scene.export(file_type="3mf"))


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


def filament_range(mesh: trimesh.Trimesh) -> tuple[float, float, float]:
    """Estimate the filament a slicer will use, in cm3, as (low, high, model).

    The model volume is exact. What the printer consumes is not, because it
    depends on perimeters, infill and how the slicer treats thin walls:

      low  - perimeters on every surface plus `infill` everywhere else. Valid
             for a chunky solid.
      high - the whole model volume, which is what a thin-walled shell costs
             because the slicer fills those walls solid.

    Reporting the range keeps the model volume from being mistaken for the
    print cost.
    """
    shell = mesh.area * PERIMETER_WIDTH_MM
    interior = max(0.0, mesh.volume - shell)
    low = shell + interior * INFILL_FRACTION
    return low / 1000, mesh.volume / 1000, mesh.volume / 1000


def report_budget(mesh: trimesh.Trimesh, label: str) -> None:
    low, high, model = filament_range(mesh)
    print(
        f"         {label}: model {model:.1f} cm3 | estimated filament "
        f"{low:.1f}-{high:.1f} cm3 at {INFILL_FRACTION:.0%} infill, "
        f"{PERIMETER_WIDTH_MM} mm perimeters"
    )


def main() -> int:
    if not FONT_PATH.exists():
        raise SystemExit(f"font not found: {FONT_PATH}")
    if ROUTE not in {"plaque", "engraved"}:
        raise SystemExit(f"unknown ROUTE {ROUTE!r}; expected 'plaque' or 'engraved'")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    font = GlyphFont(FONT_PATH)
    pedestal_spec = Pedestal()
    plaque_spec = Plaque()

    if ROUTE == "plaque":
        # Every award shares one pedestal, so it is built and verified once.
        print("pedestal (plain, shared by every award)")
        plain = build_pedestal(font, Category(slug="lisa", name="", phrase=""), pedestal_spec)
        validate(plain, "peana-lisa.stl")
        plain.export(OUT_DIR / "peana-lisa.stl")
        report_budget(plain, "peana-lisa.stl")

    # The figure is identical for every award: only the plaque changes. Both
    # candidate versions are exported so they can be printed and compared.
    print("figures (one per award, shared by every category)")
    figures = [
        ("figura-punyo", FistFigure(), build_fist),
        ("figura-punyo-cubista", FistCubist(), build_fist_cubist),
        ("figura-punyo-elegante", FistElegant(), build_fist_elegant),
        ("figura-punyo-tallado", FistCarved(), build_fist_carved),
    ]
    for slug, figure_spec, builder in figures:
        figure = builder(figure_spec)
        validate(figure, f"{slug}.stl")
        figure.export(OUT_DIR / f"{slug}.stl")
        report_budget(figure, f"{slug}.stl")
        # Report per figure: the four versions no longer share one height, and
        # printing the first one's number for all of them would misreport it.
        print(
            f"         tenon {figure_spec.tenon_width}x{figure_spec.tenon_depth}"
            f"x{figure_spec.tenon_height} mm into the {pedestal_spec.socket_width}x"
            f"{pedestal_spec.socket_depth}x{pedestal_spec.socket_recess} mm socket; "
            f"award height {pedestal_spec.height + figure_spec.top_z - figure_spec.tenon_height:.0f} mm"
        )

    for category in CATEGORIES:
        print(f"category: {category.slug}")
        if ROUTE == "engraved":
            pedestal = build_pedestal(font, category, pedestal_spec)
            validate(pedestal, f"peana-{category.slug}.stl")
            pedestal.export(OUT_DIR / f"peana-{category.slug}.stl")

        if EMIT_PLATES:
            plaque = build_plaque(font, category, plaque_spec)
            validate(plaque, f"placa-{category.slug}.stl")
            plaque.export(OUT_DIR / f"placa-{category.slug}.stl")

    # Engrave every award into the sculpture's own base.
    reference_path = OUT_DIR / "figura-referencia-100mm.stl"
    if reference_path.exists():
        print("\nengraved reference sculptures (no plate to glue)")
        base_spec = ReferenceBase()
        engraved_parts: list[tuple[str, trimesh.Trimesh]] = []
        for category in CATEGORIES:
            blank = trimesh.load(reference_path, force="mesh")
            engraved = build_engraved_reference(font, category, blank, base_spec)
            validate(engraved, f"premio-{category.slug}.stl")
            engraved.export(OUT_DIR / f"premio-{category.slug}.stl")
            report_budget(engraved, f"premio-{category.slug}.stl")
            engraved_parts.append((f"premio-{category.slug}", engraved))
        combined = OUT_DIR / "premios-8.3mf"
        write_combined_3mf(engraved_parts, combined)
        print(
            f"         {combined.name}: {combined.stat().st_size / 1e6:.1f} MB, "
            f"{len(engraved_parts)} named objects laid out on one plate"
        )
    else:
        print(f"\nno {reference_path.name}: run prepare_reference.py first")

    print(f"\n{len(CATEGORIES)} categories written to {OUT_DIR} (route: {ROUTE})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
