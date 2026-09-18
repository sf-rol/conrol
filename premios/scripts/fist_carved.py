#!/usr/bin/env python3
"""ConRol award figure, fourth version: carved from the marble in the reference.

Reconstructed from a description of the reference sculpture: white Carrara
marble, faceted low-poly with flat angular planes, upright on the wrist, fingers
curled into a loose fist, the little finger fully extended and pointing up at a
slight angle.

That look is not reachable by stacking slices. A carved marble faceting is
**few large planes meeting at sharp creases**, whereas the third version's
eighteen stacked sections produce a staircase. So this one is built the way a
carver works:

  1. **Rough out the massing** by taking the convex hull of a small set of
     section rings. Six rings of eight vertices give large facets whose angle
     changes from level to level, which is precisely the low-poly marble idiom.
  2. **Cut the concavities**, which a convex hull cannot express: the three
     grooves between the four fingers, a deep notch to free the little finger
     from the hand, and the sloping top.
  3. **Add the digits that leave the mass**, the thumb and the little finger.

Facet count is deliberately kept low. Adding sections would make it smoother and
less like stone.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import shapely.affinity
import trimesh
from shapely.geometry import Polygon

from geometry_common import BOOL_OVERSHOOT_MM, box_at, chamfered_rect, extrude, rectangular_frustum

# The rough-out: (height above the tenon, width, depth).
#
# REVISION: the first attempt made every ring the same width:depth ratio
# (1.35-1.40 across all seven levels) and a body only 1.18x taller than it was
# wide. That is, measurably, a box: uniformly scaling one rectangle at every
# height reads as a box no matter how the corners are chamfered, independently
# of anything about the pinky or the grooves. Nobody needed to see the render to
# find that - it is visible in the numbers.
#
# Fixed two ways: the height:width ratio goes from 1.18 to 1.6 (a hand is
# narrow next to how tall it stands, wrist to knuckles), and the width:depth
# ratio now varies per ring (1.52-1.75) instead of holding constant, so the hull
# is not one shape scaled uniformly seven times.
ROUGH_RINGS: tuple[tuple[float, float, float], ...] = (
    (0.0, 24.5, 14.5),
    (7.0, 21.0, 12.0),
    (16.0, 25.0, 16.5),
    (26.0, 28.0, 18.0),
    (36.0, 30.0, 19.0),
    (43.0, 28.5, 17.5),
    (48.0, 25.5, 15.5),
)


@dataclass(frozen=True)
class FistCarved:
    """Dimensions in millimetres."""

    # Socket interface, shared with the other versions.
    tenon_width: float = 30.0
    tenon_depth: float = 22.0
    tenon_height: float = 5.7

    # Roughing out.
    ring_chamfer_ratio: float = 0.26

    # Fingers: a loose fist, so the grooves are cut but not deep.
    fingers: int = 4
    groove_width: float = 2.5
    groove_depths: tuple[float, ...] = (2.4, 3.1, 2.0)
    groove_bottom_fraction: float = 0.30

    # The notch that frees the little finger from the hand. Without it the
    # reference's outline - a finger standing clear of the fist - is lost.
    separation_width: float = 3.4
    separation_depth: float = 3.6
    separation_rise: float = 13.5

    # Knuckles: facets, not blocks. A steeper pyramid than the third version's,
    # so they read as chiselled planes.
    knuckle_height: float = 4.0
    knuckle_depth: float = 8.5
    knuckle_gap: float = 1.2
    knuckle_top_scale: float = 0.50
    knuckle_rise: float = 0.8
    articulation_sink: float = 4.0
    phalange_height: float = 2.3
    phalange_depth: float = 6.5
    phalange_top_scale: float = 0.48
    phalange_center_fraction: float = 0.56

    top_tilt_deg: float = 4.0

    # Thumb, crossing the front in two faceted segments. Scaled down with the
    # slimmer hand (0.79x the old width) so it stays in proportion.
    thumb_length: float = 12.0
    thumb_thickness: float = 7.5
    thumb_depth: float = 10.0
    thumb_proud: float = 2.8
    thumb_chamfer: float = 2.1
    thumb_angle_deg: float = 14.0
    thumb_center_x: float = -5.6
    thumb_center_fraction: float = 0.30
    thumb_tip_length: float = 7.2
    thumb_tip_thickness: float = 6.2
    thumb_tip_dip_deg: float = 16.0
    thumb_tip_curl_deg: float = 11.0
    thumb_tip_overlap: float = 1.7

    # Thenar pad: the thumb-side bulge, baked into the rough-out itself (see
    # `_thenar_bump`) rather than glued on, so the side profile is not flat.
    thenar_center_fraction: float = 0.30
    thenar_proud: float = 1.9

    # Little finger: fully extended, as in the reference, so the flexion is a
    # hint rather than a curl - but it must still be measurable, because a
    # straight digit reads as a rod and not as a gesture. Slightly longer than
    # the third version's, because the reference shows it standing nearly as
    # tall as the fist itself.
    pinky_width: float = 7.3
    pinky_depth: float = 7.3
    pinky_chamfer: float = 2.1
    pinky_phalanges: tuple[float, ...] = (13.0, 10.0, 8.0)
    pinky_flexion_deg: tuple[float, ...] = (7.0, -4.0, -4.0)
    pinky_taper: float = 0.95
    pinky_lean_deg: float = 3.0
    pinky_joint_overlap: float = 2.2

    # --- derived -----------------------------------------------------------

    @property
    def body_bottom_z(self) -> float:
        return self.tenon_height

    @property
    def body_top_z(self) -> float:
        return self.tenon_height + ROUGH_RINGS[-1][0]

    @property
    def mass_bottom_z(self) -> float:
        return self.body_bottom_z

    @property
    def mass_top_z(self) -> float:
        return self.body_top_z

    @property
    def mass_width(self) -> float:
        return max(ring[1] for ring in ROUGH_RINGS)

    @property
    def mass_depth(self) -> float:
        return max(ring[2] for ring in ROUGH_RINGS)

    @property
    def front_y(self) -> float:
        return -self.mass_depth / 2

    @property
    def pinky_height(self) -> float:
        return sum(self.pinky_phalanges)

    @property
    def top_z(self) -> float:
        return self.body_top_z + self.pinky_height

    @property
    def groove_bottom_z(self) -> float:
        return self.body_bottom_z + self.groove_bottom_fraction * (
            self.body_top_z - self.body_bottom_z
        )

    @property
    def profile_check_z(self) -> float:
        return self.body_bottom_z + 0.60 * (self.body_top_z - self.body_bottom_z)

    @property
    def min_groove_depth(self) -> float:
        return min(self.groove_depths)

    @property
    def knuckle_count(self) -> int:
        return self.fingers - 1

    @property
    def nominal_pinky_area(self) -> float:
        side = self.pinky_width
        return side * self.pinky_depth - 2 * self.pinky_chamfer**2

    @property
    def pinky_column(self) -> tuple[float, float]:
        """Taken at the top of the body: the pinky rises out of that column."""
        return _columns(profile_at(ROUGH_RINGS[-1][0])[0], self.fingers)[-1]

    @property
    def pinky_center_x(self) -> float:
        left, right = self.pinky_column
        return (left + right) / 2

    @property
    def pinky_axis_start_z(self) -> float:
        return self.body_top_z + self.knuckle_rise + self.knuckle_height / 2 + 1.5


def profile_at(height_above_tenon: float) -> tuple[float, float]:
    """Interpolated width and depth of the rough-out at a given height."""
    rings = ROUGH_RINGS
    if height_above_tenon <= rings[0][0]:
        return rings[0][1], rings[0][2]
    for (z0, w0, d0), (z1, w1, d1) in zip(rings, rings[1:]):
        if height_above_tenon <= z1:
            span = z1 - z0
            local = (height_above_tenon - z0) / span if span else 0.0
            return w0 + (w1 - w0) * local, d0 + (d1 - d0) * local
    return rings[-1][1], rings[-1][2]


def _columns(width: float, fingers: int) -> list[tuple[float, float]]:
    step = width / fingers
    return [(-width / 2 + index * step, -width / 2 + (index + 1) * step) for index in range(fingers)]


def _thenar_bump(spec: FistCarved) -> tuple[float, float, float]:
    """One extra hull point: the thumb-side pad, so that side of the hand is
    not a flat plane between the wrist and the knuckle line.

    A single point pushed outward is a simplification of the thenar eminence,
    not an anatomical study, but it is enough to break the flat side and it
    costs nothing to verify: it only ever makes the hull wider on one side.
    """
    height = spec.thenar_center_fraction * ROUGH_RINGS[-1][0]
    width, depth = profile_at(height)
    return (-width / 2 - spec.thenar_proud, -depth * 0.1, spec.tenon_height + height)


def _rough_out(spec: FistCarved) -> trimesh.Trimesh:
    """Convex hull of the section rings: the carved block before any cutting.

    A hull can only be convex, so everything concave - grooves, the notch that
    frees the little finger, the sloping top - has to be cut afterwards. That is
    also the order a carver works in, and it is why the facets stay large: no
    amount of hulling adds detail.
    """
    points: list[tuple[float, float, float]] = []
    for height, width, depth in ROUGH_RINGS:
        ring = chamfered_rect(width, depth, spec.ring_chamfer_ratio * min(width, depth))
        points.extend((x, y, spec.tenon_height + height) for x, y in ring.exterior.coords[:-1])
    points.append(_thenar_bump(spec))
    hull = trimesh.Trimesh(vertices=np.array(points, dtype=float), process=False).convex_hull
    return hull


def _tenon(spec: FistCarved) -> trimesh.Trimesh:
    height = spec.tenon_height + 1.0
    return box_at((spec.tenon_width, spec.tenon_depth, height), (0.0, 0.0, height / 2))


def _groove_cutters(spec: FistCarved) -> list[trimesh.Trimesh]:
    """Three wedge grooves between the four finger columns."""
    height = spec.body_top_z - spec.groove_bottom_z + 2 * BOOL_OVERSHOOT_MM
    top_width = profile_at(ROUGH_RINGS[-1][0])[0]
    boundaries = [right for _, right in _columns(top_width, spec.fingers)[:-1]]
    open_y = spec.front_y - 1.5
    cutters = []
    for boundary, depth in zip(boundaries, spec.groove_depths):
        half = spec.groove_width / 2
        wedge = Polygon(
            [(boundary - half, open_y), (boundary + half, open_y), (boundary, spec.front_y + depth)]
        )
        cutters.append(extrude(wedge, height, base_z=spec.groove_bottom_z))
    return cutters


def _separation_cutter(spec: FistCarved) -> trimesh.Trimesh:
    """The notch that stands the little finger clear of the hand."""
    boundary = spec.pinky_column[0]
    half = spec.separation_width / 2
    open_y = spec.front_y - 2.0
    base_z = spec.body_top_z - 5.0
    wedge = Polygon(
        [
            (boundary - half, open_y),
            (boundary + half, open_y),
            (boundary + half * 0.3, spec.front_y + spec.separation_depth),
            (boundary - half * 0.3, spec.front_y + spec.separation_depth),
        ]
    )
    return extrude(wedge, spec.separation_rise, base_z=base_z)


def _top_tilt_cutter(spec: FistCarved) -> trimesh.Trimesh:
    cutter = box_at((200.0, 200.0, 60.0), (0.0, 0.0, spec.body_top_z + 30.0))
    cutter.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(spec.top_tilt_deg), [0.0, 1.0, 0.0], point=[0.0, 0.0, spec.body_top_z]
        )
    )
    return cutter


def _articulation_row(
    spec: FistCarved,
    center_z: float,
    height: float,
    depth: float,
    top_scale: float,
    follow_top_tilt: bool = False,
) -> list[trimesh.Trimesh]:
    """A row of chiselled facets on every column but the pinky's.

    The pinky column is left bare so the raised finger is visibly the fourth one
    along, which is what names it the little finger.
    """
    above = center_z - spec.tenon_height
    width = profile_at(above)[0]
    base_z = center_z - height / 2
    blocks = []
    for left, right in _columns(width, spec.fingers)[:-1]:
        block_width = (right - left) - spec.knuckle_gap
        block = rectangular_frustum(
            (block_width, depth),
            (block_width * top_scale, depth * top_scale),
            height,
            base_z=base_z,
        )
        block.apply_translation([(left + right) / 2, spec.front_y + depth / 2 - 1.0, 0.0])
        if follow_top_tilt:
            block.apply_transform(
                trimesh.transformations.rotation_matrix(
                    math.radians(spec.top_tilt_deg),
                    [0.0, 1.0, 0.0],
                    point=[0.0, 0.0, spec.body_top_z],
                )
            )
        anchor = box_at(
            (block_width, depth, spec.articulation_sink),
            [
                (left + right) / 2,
                spec.front_y + depth / 2 - 1.0,
                base_z - spec.articulation_sink / 2,
            ],
        )
        blocks.append(trimesh.boolean.union([block, anchor], engine="manifold"))
    return blocks


def _thumb(spec: FistCarved) -> trimesh.Trimesh:
    upright = trimesh.transformations.rotation_matrix(1.5707963, [1.0, 0.0, 0.0])
    place = trimesh.transformations.translation_matrix(
        [
            spec.thumb_center_x,
            spec.front_y - spec.thumb_proud + spec.thumb_depth,
            spec.body_bottom_z + spec.thumb_center_fraction * (spec.body_top_z - spec.body_bottom_z),
        ]
    ) @ trimesh.transformations.rotation_matrix(
        math.radians(spec.thumb_angle_deg), [0.0, 1.0, 0.0]
    )

    proximal = extrude(
        chamfered_rect(spec.thumb_length, spec.thumb_thickness, spec.thumb_chamfer),
        spec.thumb_depth,
    )
    proximal.apply_transform(place @ upright)

    joint = place @ trimesh.transformations.translation_matrix(
        [spec.thumb_length / 2 - spec.thumb_tip_overlap, 0.0, 0.0]
    )
    joint = joint @ trimesh.transformations.rotation_matrix(
        math.radians(spec.thumb_tip_dip_deg), [0.0, 1.0, 0.0]
    )
    joint = joint @ trimesh.transformations.rotation_matrix(
        math.radians(spec.thumb_tip_curl_deg), [0.0, 0.0, 1.0]
    )
    distal = extrude(
        chamfered_rect(spec.thumb_tip_length, spec.thumb_tip_thickness, spec.thumb_chamfer * 0.85),
        spec.thumb_depth * 0.86,
    )
    distal.apply_transform(
        joint
        @ trimesh.transformations.translation_matrix([spec.thumb_tip_length / 2, 0.0, 0.0])
        @ upright
    )
    return trimesh.boolean.union([proximal, distal], engine="manifold")


def _pinky(spec: FistCarved) -> trimesh.Trimesh:
    """Three phalanges, nearly straight, each joint flexed a few degrees."""
    profile = chamfered_rect(spec.pinky_width, spec.pinky_depth, spec.pinky_chamfer)
    frame = trimesh.transformations.translation_matrix(
        [spec.pinky_center_x, 0.0, spec.body_top_z]
    ) @ trimesh.transformations.rotation_matrix(
        math.radians(spec.pinky_lean_deg), [0.0, 1.0, 0.0]
    )

    parts = []
    for index, length in enumerate(spec.pinky_phalanges):
        frame = frame @ trimesh.transformations.rotation_matrix(
            math.radians(spec.pinky_flexion_deg[index]), [1.0, 0.0, 0.0]
        )
        taper = spec.pinky_taper**index
        embed = BOOL_OVERSHOOT_MM * 5 if index == 0 else spec.pinky_joint_overlap
        piece = extrude(
            shapely.affinity.scale(profile, xfact=taper, yfact=taper, origin="center"),
            length + embed,
            base_z=-embed,
        )
        piece.apply_transform(frame)
        parts.append(piece)
        frame = frame @ trimesh.transformations.translation_matrix([0.0, 0.0, length])
    return trimesh.boolean.union(parts, engine="manifold")


def build_fist_carved(spec: FistCarved | None = None) -> trimesh.Trimesh:
    """The carved figure, origin at the bottom of the tenon.

    Rough out convex, cut the concavities, then add the digits that leave the
    mass. Cutting the top last would take the little finger off at the knuckles,
    which is the mistake the second version made.
    """
    spec = spec or FistCarved()
    body = trimesh.boolean.union([_tenon(spec), _rough_out(spec)], engine="manifold")
    body = trimesh.boolean.difference(
        [
            body,
            *_groove_cutters(spec),
            _separation_cutter(spec),
            _top_tilt_cutter(spec),
        ],
        engine="manifold",
    )
    return trimesh.boolean.union(
        [
            body,
            *_articulation_row(
                spec,
                center_z=spec.body_top_z + spec.knuckle_rise,
                height=spec.knuckle_height,
                depth=spec.knuckle_depth,
                top_scale=spec.knuckle_top_scale,
                follow_top_tilt=True,
            ),
            *_articulation_row(
                spec,
                center_z=spec.body_bottom_z
                + spec.phalange_center_fraction * (spec.body_top_z - spec.body_bottom_z),
                height=spec.phalange_height,
                depth=spec.phalange_depth,
                top_scale=spec.phalange_top_scale,
            ),
            _thumb(spec),
            _pinky(spec),
        ],
        engine="manifold",
    )
