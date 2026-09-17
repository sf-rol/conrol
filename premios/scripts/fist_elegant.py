#!/usr/bin/env python3
"""ConRol award figure, third version: built from scratch to DESIGN-BRIEF.md.

Not a variation on the earlier two. The earlier ones are a box with slots cut in
it; this one starts from the two things the brief asks for that they lack:

  * a hand that **tapers**, because a hand is narrow at the wrist and widest
    across the knuckles. The body is a stack of sections interpolated along an
    anatomical profile, so the silhouette swells and the facets follow it.
  * **articulation at two rows**, not one. Three knuckles along the top and a
    second row of proximal interphalangeal joints below them. A fist with one row
    of bumps reads as a box.

The little finger is the hero and is articulated into three phalanges with a
flexion at every joint, so it forms the shallow S-curve of a real extended
pinky instead of a stiff rod. Three knuckles plus one articulated finger beyond
them is what names it: the raised digit must read as the fourth one along.

Style budget from the brief: about 60% faceted planes, 40% observed anatomy.
Facets come from the chamfered octagonal plan, the stepped section stack, and
truncated-pyramid blocks; anatomy comes from the profile, the joint rows, the
thumb crossing the front, and the thenar and hypothenar pads.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import shapely.affinity
import trimesh
from shapely.geometry import Polygon

from geometry_common import BOOL_OVERSHOOT_MM, box_at, chamfered_rect, extrude, rectangular_frustum

# (fraction of the body height, width, depth) - the silhouette of a hand from
# the wrist up: pinched, then swelling to the knuckle line, then easing off.
BODY_PROFILE: tuple[tuple[float, float, float], ...] = (
    (0.00, 31.5, 23.5),
    (0.20, 30.0, 22.0),
    (0.40, 34.0, 24.5),
    (0.72, 38.0, 27.5),
    (1.00, 36.5, 26.5),
)


@dataclass(frozen=True)
class FistElegant:
    """Dimensions in millimetres."""

    # Socket interface, shared with the other versions.
    tenon_width: float = 30.0
    tenon_depth: float = 22.0
    tenon_height: float = 5.7

    # Tapered body.
    body_height: float = 45.0
    body_slices: int = 18
    chamfer_ratio: float = 0.19

    # Fingers.
    fingers: int = 4
    groove_width: float = 2.8
    groove_depths: tuple[float, ...] = (2.6, 3.4, 2.1)
    groove_bottom_fraction: float = 0.24

    # Knuckle row (metacarpophalangeal) and second row (proximal interphalangeal).
    knuckle_height: float = 5.0
    knuckle_depth: float = 11.0
    knuckle_gap: float = 1.2
    knuckle_top_scale: float = 0.70
    knuckle_rise: float = 1.0
    phalange_height: float = 2.8
    phalange_depth: float = 8.5
    phalange_top_scale: float = 0.55
    # Every articulation block sinks this far into the body through a hidden
    # anchor prism. Without it a block whose bottom happens to land close to a
    # sloping top face ends up floating, which is exactly what happened to the
    # index knuckle on the first build.
    articulation_sink: float = 4.0
    # Above the thumb, not under it: in a relaxed fist gripping a handle the
    # thumb rests lower, which is also what keeps this second row visible. It is
    # a deliberate stylisation - the row is what stops the fist reading as a box.
    phalange_center_fraction: float = 0.55

    # Top face, sloping down towards the pinky: the knuckle line descends from
    # the index to the little finger, which is also what gives the pinky further
    # to travel to stand proud.
    top_tilt_deg: float = 5.0

    # Thumb, crossing the front in two segments.
    thumb_length: float = 15.0
    thumb_thickness: float = 8.5
    thumb_depth: float = 12.0
    thumb_proud: float = 3.6
    thumb_chamfer: float = 2.2
    thumb_angle_deg: float = 14.0
    thumb_center_x: float = -8.0
    thumb_center_fraction: float = 0.30
    thumb_tip_length: float = 9.0
    thumb_tip_thickness: float = 7.5
    thumb_tip_dip_deg: float = 17.0
    thumb_tip_curl_deg: float = 11.0
    thumb_tip_overlap: float = 2.0

    # Hypothenar pad: the little-finger side of the palm. Easy to forget, and it
    # is what tells the eye which side of the hand it is looking at.
    hypothenar_center_fraction: float = 0.34
    hypothenar_size: tuple[float, float, float] = (15.0, 15.0, 13.0)
    hypothenar_proud: float = 1.1

    # The little finger: three phalanges, flexion at every joint.
    pinky_width: float = 8.0
    pinky_depth: float = 8.0
    pinky_chamfer: float = 2.4
    pinky_phalanges: tuple[float, ...] = (11.5, 9.0, 7.5)
    pinky_flexion_deg: tuple[float, ...] = (8.0, -5.0, -6.0)
    pinky_taper: float = 0.94
    pinky_lean_deg: float = 5.0
    # Enough overlap that the wedge a flexion opens on the inside of the bend
    # never becomes a gap. At 1.2 mm it left a 0.17 mm2 sliver in the section.
    pinky_joint_overlap: float = 2.5

    # --- derived -----------------------------------------------------------

    @property
    def body_bottom_z(self) -> float:
        return self.tenon_height

    @property
    def body_top_z(self) -> float:
        return self.tenon_height + self.body_height

    @property
    def mass_bottom_z(self) -> float:
        """Kept for the shared verification interface: the body is one piece."""
        return self.body_bottom_z

    @property
    def mass_top_z(self) -> float:
        return self.body_top_z

    @property
    def mass_width(self) -> float:
        return max(entry[1] for entry in BODY_PROFILE)

    @property
    def mass_depth(self) -> float:
        return max(entry[2] for entry in BODY_PROFILE)

    @property
    def pinky_height(self) -> float:
        return sum(self.pinky_phalanges)

    @property
    def top_z(self) -> float:
        return self.body_top_z + self.pinky_height

    @property
    def front_y(self) -> float:
        return -self.mass_depth / 2

    @property
    def groove_bottom_z(self) -> float:
        return self.body_bottom_z + self.groove_bottom_fraction * self.body_height

    @property
    def profile_check_z(self) -> float:
        """Clear of the thumb and both articulation rows, inside the grooves."""
        return self.body_bottom_z + 0.62 * self.body_height

    @property
    def min_groove_depth(self) -> float:
        return min(self.groove_depths)

    @property
    def knuckle_count(self) -> int:
        return self.fingers - 1

    @property
    def pinky_axis_start_z(self) -> float:
        """Above the knuckle row, or the axis samples see more than the pinky."""
        return self.body_top_z + self.knuckle_rise + self.knuckle_height / 2 + 1.5

    @property
    def nominal_pinky_area(self) -> float:
        side = self.pinky_width
        return side * self.pinky_depth - 2 * self.pinky_chamfer**2

    @property
    def pinky_column(self) -> tuple[float, float]:
        return _columns(self.mass_width, self.fingers)[-1]

    @property
    def pinky_center_x(self) -> float:
        left, right = self.pinky_column
        return (left + right) / 2


def _columns(width: float, fingers: int) -> list[tuple[float, float]]:
    step = width / fingers
    return [(-width / 2 + index * step, -width / 2 + (index + 1) * step) for index in range(fingers)]


def profile_at(fraction: float) -> tuple[float, float]:
    """Width and depth of the body at a fraction of its height."""
    points = BODY_PROFILE
    if fraction <= points[0][0]:
        return points[0][1], points[0][2]
    for (t0, w0, d0), (t1, w1, d1) in zip(points, points[1:]):
        if fraction <= t1:
            span = t1 - t0
            local = (fraction - t0) / span if span else 0.0
            # Ease out, so the swell happens low and the upper body stays calm.
            eased = 1.0 - (1.0 - local) ** 1.6
            return w0 + (w1 - w0) * eased, d0 + (d1 - d0) * eased
    return points[-1][1], points[-1][2]


def _plan(spec: FistElegant, width: float, depth: float) -> Polygon:
    return chamfered_rect(width, depth, spec.chamfer_ratio * min(width, depth))


def _tenon(spec: FistElegant) -> trimesh.Trimesh:
    height = spec.tenon_height + 1.0
    return box_at((spec.tenon_width, spec.tenon_depth, height), (0.0, 0.0, height / 2))


def _body(spec: FistElegant) -> trimesh.Trimesh:
    """The tapered hand: a stack of chamfered sections along the hand profile.

    Each section is a vertical prism, so the surface steps outward by well under
    a millimetre per slice and prints without support while still reading as a
    faceted sweep rather than a smooth surface.
    """
    slices = max(4, spec.body_slices)
    step = spec.body_height / slices
    parts = []
    for index in range(slices):
        fraction = (index + 0.5) / slices
        width, depth = profile_at(fraction)
        parts.append(
            extrude(
                _plan(spec, width, depth),
                step + 0.02,
                base_z=spec.body_bottom_z + index * step,
            )
        )
    return trimesh.boolean.union(parts, engine="manifold")


def _groove_cutters(spec: FistElegant) -> list[trimesh.Trimesh]:
    """Wedge grooves between the finger columns, from the palm to the top."""
    height = spec.body_top_z - spec.groove_bottom_z + 2 * BOOL_OVERSHOOT_MM
    columns = _columns(spec.mass_width, spec.fingers)
    boundaries = [right for _, right in columns[:-1]]
    opening_y = spec.front_y - 1.5
    cutters = []
    for boundary, depth in zip(boundaries, spec.groove_depths):
        half = spec.groove_width / 2
        wedge = Polygon(
            [
                (boundary - half, opening_y),
                (boundary + half, opening_y),
                (boundary, spec.front_y + depth),
            ]
        )
        cutters.append(extrude(wedge, height, base_z=spec.groove_bottom_z))
    return cutters


def _top_tilt_cutter(spec: FistElegant) -> trimesh.Trimesh:
    """A slab whose underside becomes the top face, sloping down to the pinky."""
    cutter = box_at((200.0, 200.0, 60.0), (0.0, 0.0, spec.body_top_z + 30.0))
    cutter.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(spec.top_tilt_deg), [0.0, 1.0, 0.0], point=[0.0, 0.0, spec.body_top_z]
        )
    )
    return cutter


def _articulation_row(
    spec: FistElegant,
    center_z: float,
    height: float,
    depth: float,
    top_scale: float,
    follow_top_tilt: bool = False,
) -> list[trimesh.Trimesh]:
    """One row of truncated-pyramid blocks, on every column but the pinky's.

    Index, middle and ring get a block; the little finger's column is left bare
    so the raised pinky emerges from it. That bare column is the whole reason
    the raised finger reads as the pinky.
    """
    fraction = (center_z - spec.body_bottom_z) / spec.body_height
    width, _ = profile_at(fraction)
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
            # Ride the sloping top, or the row is buried on one side of the hand
            # and floating on the other.
            block.apply_transform(
                trimesh.transformations.rotation_matrix(
                    math.radians(spec.top_tilt_deg),
                    [0.0, 1.0, 0.0],
                    point=[0.0, 0.0, spec.body_top_z],
                )
            )
        anchor = box_at(
            (block_width, depth, spec.articulation_sink),
            [(left + right) / 2, spec.front_y + depth / 2 - 1.0, base_z - spec.articulation_sink / 2],
        )
        blocks.append(trimesh.boolean.union([block, anchor], engine="manifold"))
    return blocks


def _thumb(spec: FistElegant) -> trimesh.Trimesh:
    """Two chamfered segments with a joint, so the thumb is not one brick."""
    upright = trimesh.transformations.rotation_matrix(1.5707963, [1.0, 0.0, 0.0])
    place = trimesh.transformations.translation_matrix(
        [
            spec.thumb_center_x,
            spec.front_y - spec.thumb_proud + spec.thumb_depth,
            spec.body_bottom_z + spec.thumb_center_fraction * spec.body_height,
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
        chamfered_rect(
            spec.thumb_tip_length, spec.thumb_tip_thickness, spec.thumb_chamfer * 0.85
        ),
        spec.thumb_depth * 0.86,
    )
    distal.apply_transform(
        joint
        @ trimesh.transformations.translation_matrix([spec.thumb_tip_length / 2, 0.0, 0.0])
        @ upright
    )
    return trimesh.boolean.union([proximal, distal], engine="manifold")


def _hypothenar(spec: FistElegant) -> trimesh.Trimesh:
    """A faceted swelling on the little-finger side of the palm."""
    fraction = spec.hypothenar_center_fraction
    width, depth = profile_at(fraction)
    size_x, size_y, size_z = spec.hypothenar_size
    pad = extrude(chamfered_rect(size_x, size_y, spec.chamfer_ratio * size_y), size_z)
    pad.apply_translation(
        [
            width / 2 - size_x / 2 + spec.hypothenar_proud,
            -depth * 0.1,
            spec.body_bottom_z + fraction * spec.body_height - size_z / 2,
        ]
    )
    return pad


def _pinky(spec: FistElegant) -> trimesh.Trimesh:
    """Three phalanges, each joint flexed, forming the shallow S of a real pinky.

    The transform is walked forward joint by joint, which is the only way to get
    an articulated finger that actually bends at its joints instead of being a
    bent stick.
    """
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


def build_fist_elegant(spec: FistElegant | None = None) -> trimesh.Trimesh:
    """The tapered, articulated figure, origin at the bottom of the tenon.

    The grooves and the sloping top are cut into the bare body first; the
    articulation rows, the thumb, the pad and the pinky are unioned afterwards,
    so the top cut cannot slice the pinky off at the knuckles.
    """
    spec = spec or FistElegant()
    # Pull the body 1 mm down so it swallows the top of the tenon.
    body = trimesh.boolean.union(
        [_tenon(spec), _body(spec)], engine="manifold"
    )
    body = trimesh.boolean.difference(
        [body, *_groove_cutters(spec), _top_tilt_cutter(spec)], engine="manifold"
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
                center_z=spec.body_bottom_z + spec.phalange_center_fraction * spec.body_height,
                height=spec.phalange_height,
                depth=spec.phalange_depth,
                top_scale=spec.phalange_top_scale,
            ),
            _thumb(spec),
            _hypothenar(spec),
            _pinky(spec),
        ],
        engine="manifold",
    )
