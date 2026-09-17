#!/usr/bin/env python3
"""ConRol award figure, second version: the same fist, faceted into cubism.

Kept alongside `fist_figure.py` on purpose, so both can be printed and compared.
This one starts from the same anatomy and the same socket, then stylises it.

The cubist devices are all printable without supports, because every one of them
is either a vertical wall, a top surface, or a step small enough to bridge:

  * **Faceted silhouette.** The body plan is an octagon, not a rectangle, so the
    outline breaks into planes that catch the light differently.
  * **Shattered front plane.** The four finger panels sit at four different
    depths, in a gentle staircase, so the front is not one flat face but four.
    These are vertical walls, so nothing overhangs.
  * **Rotated top.** The top face is cut at a slight angle, higher on the pinky
    side, which tips the whole form and reads as a second viewpoint.
  * **Displaced volumes.** The wrist is a stack of progressively scaled copies
    of the body plan rather than a smooth taper, and the pinky is two segments
    offset from each other. Both are the cubist idiom of a form that has been
    shifted and reassembled.
  * **Unequal grooves.** The three grooves differ in depth instead of being
    identical, so the fingers never look machine-tiled.

Readability of the pinky is the one thing that must not be sacrificed to style.
Three things carry it, in order of how much they matter:

  1. three **knuckle blocks** sit on top of the index, middle and ring columns,
     and the pinky column has none - the raised finger is the fourth one along,
     which is what makes it the pinky rather than a nameless finger
  2. the thumb is on the opposite side, which fixes the handedness
  3. the pinky is the **narrowest** column and is articulated into two visible
     segments, because the pinky is the small finger
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import shapely.affinity
import trimesh
from shapely.geometry import Polygon

from geometry_common import (
    BOOL_OVERSHOOT_MM,
    box_at,
    chamfered_rect,
    extrude,
    rectangular_frustum,
)


@dataclass(frozen=True)
class FistCubist:
    """Dimensions in millimetres. Same socket as the first version."""

    # Socket interface: identical to fist_figure.FistFigure, on purpose.
    tenon_width: float = 30.0
    tenon_depth: float = 22.0
    tenon_height: float = 5.7

    # Wrist: a stepped stack of scaled body plans, not a smooth taper.
    wrist_height: float = 10.0
    wrist_steps: int = 8
    wrist_scale_bottom: float = 0.78

    # Body.
    mass_width: float = 40.0
    mass_depth: float = 30.0
    mass_height: float = 38.0
    corner_chamfer: float = 5.0
    front_chamfer: float = 3.0

    # Fingers: four panels at four depths, separated by unequal grooves.
    fingers: int = 4
    finger_proud: tuple[float, ...] = (0.0, 0.6, 1.2, 1.8)
    groove_width: float = 3.2
    groove_depths: tuple[float, ...] = (2.8, 3.8, 2.2)
    groove_bottom_z: float = 33.0

    # Knuckles: on the first three columns only. This is what says "pinky".
    knuckle_height: float = 4.5
    knuckle_depth: float = 16.0
    knuckle_gap: float = 1.4
    knuckle_top_scale: float = 0.62

    # Rotated top face.
    top_tilt_deg: float = 4.0

    # Thumb, a faceted slab crossing the lower front.
    thumb_length: float = 27.0
    thumb_thickness: float = 9.5
    thumb_depth: float = 13.0
    thumb_proud: float = 4.0
    thumb_chamfer: float = 2.5
    thumb_angle_deg: float = 16.0
    thumb_center_x: float = -5.0
    thumb_center_z: float = 25.0

    # Pinky: two chamfered segments, offset, plus a facet tip.
    pinky_width: float = 8.6
    pinky_depth: float = 8.6
    pinky_chamfer: float = 2.0
    pinky_segments: tuple[float, ...] = (12.0, 11.0)
    pinky_segment_offset: tuple[float, float] = (0.7, -0.4)
    pinky_tip_height: float = 3.0
    pinky_tip_taper: float = 2.6
    pinky_lean_deg: float = 6.0

    # --- derived -----------------------------------------------------------

    @property
    def mass_bottom_z(self) -> float:
        return self.tenon_height + self.wrist_height

    @property
    def mass_top_z(self) -> float:
        return self.mass_bottom_z + self.mass_height

    @property
    def pinky_height(self) -> float:
        return sum(self.pinky_segments) + self.pinky_tip_height

    @property
    def top_z(self) -> float:
        return self.mass_top_z + self.pinky_height

    @property
    def finger_boundaries_x(self) -> list[float]:
        step = self.mass_width / self.fingers
        return [-self.mass_width / 2 + index * step for index in range(1, self.fingers)]

    @property
    def finger_columns(self) -> list[tuple[float, float]]:
        step = self.mass_width / self.fingers
        return [
            (-self.mass_width / 2 + index * step, -self.mass_width / 2 + (index + 1) * step)
            for index in range(self.fingers)
        ]

    @property
    def pinky_column(self) -> tuple[float, float]:
        return self.finger_columns[-1]

    @property
    def pinky_center_x(self) -> float:
        left, right = self.pinky_column
        return (left + right) / 2

    @property
    def front_y(self) -> float:
        return -self.mass_depth / 2

    @property
    def groove_depth(self) -> float:
        """Deepest groove, used for documentation and the wedge profile."""
        return max(self.groove_depths)

    @property
    def min_groove_depth(self) -> float:
        """Shallowest groove: a slab cut must sit in front of it to open them all."""
        return min(self.groove_depths)

    @property
    def nominal_pinky_area(self) -> float:
        side = self.pinky_width
        return side * self.pinky_depth - 2 * self.pinky_chamfer**2

    @property
    def knuckle_count(self) -> int:
        """One knuckle per column except the pinky column, which is left bare."""
        return self.fingers - 1


def body_plan(spec: FistCubist) -> Polygon:
    """The horizontal cross-section: a chamfered octagon with a stepped front.

    Each finger column's front face sits at its own depth, so the front plane is
    broken into four. Those offsets only ever move a panel forward or back, so
    every resulting surface is vertical and needs no support.
    """
    half_w, half_d = spec.mass_width / 2, spec.mass_depth / 2
    front_y = spec.front_y
    proud = spec.finger_proud
    cut = spec.corner_chamfer
    front_cut = spec.front_chamfer

    ring: list[tuple[float, float]] = []
    for index, (left, right) in enumerate(spec.finger_columns):
        panel_y = front_y - proud[index]
        if index == 0:
            ring.append((left + front_cut, panel_y))
        else:
            # The step from the previous panel: a vertical wall, no overhang.
            ring.append((left, front_y - proud[index - 1]))
            ring.append((left, panel_y))
        ring.append((right, panel_y))

    ring += [
        (half_w, half_d - cut),
        (half_w - cut, half_d),
        (-half_w + cut, half_d),
        (-half_w, half_d - cut),
        (-half_w, front_y - proud[0] + front_cut),
    ]
    plan = Polygon(_dedupe(ring))
    if not plan.is_valid:
        plan = plan.buffer(0)
    return plan


def _dedupe(ring: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Drop consecutive duplicate vertices, which shapely dislikes."""
    out: list[tuple[float, float]] = []
    for point in ring:
        if not out or abs(point[0] - out[-1][0]) > 1e-9 or abs(point[1] - out[-1][1]) > 1e-9:
            out.append(point)
    return out


def _tenon(spec: FistCubist) -> trimesh.Trimesh:
    height = spec.tenon_height + 1.0
    return box_at((spec.tenon_width, spec.tenon_depth, height), (0.0, 0.0, height / 2))


def _wrist(spec: FistCubist) -> trimesh.Trimesh:
    """A stepped stack of scaled body plans.

    A smooth taper would be the obvious choice and the wrong one: scaling the
    plan keeps the octagonal facets running all the way down, and the steps are
    the cubist gesture. Each ledge is under a millimetre, well inside what FDM
    bridges without support.
    """
    plan = body_plan(spec)
    steps = max(2, spec.wrist_steps)
    step_height = spec.wrist_height / steps
    parts = []
    for index in range(steps):
        fraction = index / (steps - 1)
        scale = spec.wrist_scale_bottom + (1.0 - spec.wrist_scale_bottom) * fraction
        scaled = shapely.affinity.scale(plan, xfact=scale, yfact=scale, origin="center")
        parts.append(
            extrude(
                scaled,
                step_height + 0.02,
                base_z=spec.tenon_height + index * step_height,
            )
        )
    return trimesh.boolean.union(parts, engine="manifold")


def _body(spec: FistCubist) -> trimesh.Trimesh:
    height = spec.mass_height + BOOL_OVERSHOOT_MM + 0.5
    return extrude(body_plan(spec), height, base_z=spec.mass_bottom_z - 0.5)


def _groove_cutters(spec: FistCubist) -> list[trimesh.Trimesh]:
    """Wedge-shaped, unequal, cutting the front face from the knuckles upwards.

    A wedge rather than a square slot: the crease between two fingers catches
    light far better than a flat-bottomed channel, which is the whole point.
    """
    height = spec.mass_top_z - spec.groove_bottom_z + 2 * BOOL_OVERSHOOT_MM
    base_z = spec.groove_bottom_z
    opening_y = spec.front_y - max(spec.finger_proud) - 1.5
    cutters = []
    for boundary, depth in zip(spec.finger_boundaries_x, spec.groove_depths):
        half = spec.groove_width / 2
        wedge = Polygon(
            [
                (boundary - half, opening_y),
                (boundary + half, opening_y),
                (boundary, spec.front_y + depth),
            ]
        )
        cutters.append(extrude(wedge, height, base_z=base_z))
    return cutters


def _top_tilt_cutter(spec: FistCubist) -> trimesh.Trimesh:
    """An angled slab whose underside becomes the top face.

    Rotated so the top rises towards the pinky side, tipping the form and
    showing two planes where a box would show one.
    """
    size = 200.0
    cutter = box_at((size, size, 60.0), (0.0, 0.0, spec.mass_top_z + 30.0))
    cutter.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(-spec.top_tilt_deg), [0.0, 1.0, 0.0], point=[0.0, 0.0, spec.mass_top_z]
        )
    )
    return cutter


def _knuckles(spec: FistCubist) -> list[trimesh.Trimesh]:
    """Three faceted knuckle blocks, on the first three columns only.

    The fourth column is left bare so the pinky rises out of it. Three knuckles
    in a row next to one raised finger is what makes that finger the pinky.
    """
    blocks = []
    base_z = spec.mass_top_z - 3.5
    height = spec.mass_top_z + spec.knuckle_height - base_z
    for index, (left, right) in enumerate(spec.finger_columns[:-1]):
        width = (right - left) - spec.knuckle_gap
        center_x = (left + right) / 2
        center_y = spec.front_y - spec.finger_proud[index] + spec.knuckle_depth / 2
        block = rectangular_frustum(
            (width, spec.knuckle_depth),
            (width * spec.knuckle_top_scale, spec.knuckle_depth * spec.knuckle_top_scale),
            height,
            base_z=base_z,
        )
        block.apply_translation([center_x, center_y, 0.0])
        blocks.append(block)
    return blocks


def _thumb(spec: FistCubist) -> trimesh.Trimesh:
    """A chamfered slab, so the thumb is a faceted plane and not a brick."""
    profile = chamfered_rect(spec.thumb_length, spec.thumb_thickness, spec.thumb_chamfer)
    slab = extrude(profile, spec.thumb_depth)
    # (x, y, z) -> (x, -z, y): the chamfered profile moves into the XZ plane and
    # the extrusion runs along -Y, which is where the thumb has to protrude.
    slab.apply_transform(trimesh.transformations.rotation_matrix(1.5707963, [1.0, 0.0, 0.0]))

    # After that rotation the slab spans Y in [-depth, 0], so translating by
    # (front - proud + depth) puts its face at `thumb_proud` in front of the body.
    center_y = spec.front_y - spec.thumb_proud + spec.thumb_depth
    slab.apply_translation([spec.thumb_center_x, center_y, spec.thumb_center_z])
    slab.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(spec.thumb_angle_deg),
            [0.0, 1.0, 0.0],
            point=[spec.thumb_center_x, center_y, spec.thumb_center_z],
        )
    )
    return slab


def _pinky(spec: FistCubist) -> trimesh.Trimesh:
    """Two chamfered segments, displaced from each other, plus a faceted tip.

    Z is advanced by the nominal segment heights from the top of the body, so
    the assembled pinky is exactly `pinky_height` tall and `top_z` stays true.
    """
    profile = chamfered_rect(spec.pinky_width, spec.pinky_depth, spec.pinky_chamfer)
    parts: list[trimesh.Trimesh] = []
    z = spec.mass_top_z
    for index, segment in enumerate(spec.pinky_segments):
        embed = 2.0 if index == 0 else 0.0  # sink the base into the body
        # The profile is centred on the origin, so it has to be moved onto its
        # own finger column before anything else happens to it.
        piece = extrude(profile, segment + embed, base_z=z - embed)
        piece.apply_translation([spec.pinky_center_x, 0.0, 0.0])
        if index > 0:
            piece.apply_translation(
                [spec.pinky_segment_offset[0], spec.pinky_segment_offset[1], 0.0]
            )
        parts.append(piece)
        z += segment

    tip = rectangular_frustum(
        (spec.pinky_width, spec.pinky_depth),
        (
            spec.pinky_width - spec.pinky_tip_taper,
            spec.pinky_depth - spec.pinky_tip_taper,
        ),
        spec.pinky_tip_height,
        base_z=z,
    )
    tip.apply_translation(
        [
            spec.pinky_center_x + spec.pinky_segment_offset[0],
            spec.pinky_segment_offset[1],
            0.0,
        ]
    )
    parts.append(tip)

    pinky = trimesh.boolean.union(parts, engine="manifold")
    pinky.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(spec.pinky_lean_deg),
            [0.0, 1.0, 0.0],
            point=[spec.pinky_center_x, 0.0, spec.mass_top_z],
        )
    )
    return pinky


def build_fist_cubist(spec: FistCubist | None = None) -> trimesh.Trimesh:
    """The faceted figure, with its origin at the bottom of the tenon.

    Order matters. The grooves and the angled top are cut into the body while
    it is still bare, and the knuckles, thumb and pinky are unioned afterwards.
    Cutting the top last would slice the pinky off at the knuckles, which is
    exactly what happened the first time this was written.
    """
    spec = spec or FistCubist()
    body = trimesh.boolean.union(
        [_tenon(spec), _wrist(spec), _body(spec)], engine="manifold"
    )
    body = trimesh.boolean.difference(
        [body, *_groove_cutters(spec), _top_tilt_cutter(spec)], engine="manifold"
    )
    return trimesh.boolean.union(
        [body, *_knuckles(spec), _thumb(spec), _pinky(spec)], engine="manifold"
    )
