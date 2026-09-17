#!/usr/bin/env python3
"""The ConRol award figure: a closed fist with the pinky raised.

Modelled as a solid, not sculpted. The style is deliberately geometric and
minimalist, which is what makes it buildable from primitives, but the anatomy
is still readable from a distance:

  * four finger columns across the front face, separated by three vertical
    grooves that also cut the top edge, so they read as knuckles from above
  * a thumb crossing the lower front, angled, wrapping over the fingers
  * a wrist that flares from the tenon up into the body
  * the outermost finger column - the pinky - rising clear of the fist

Frame: X is width, Y is depth, Z is up. The origin is the bottom of the tenon,
so the figure can be dropped straight into the pedestal socket.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import trimesh

from geometry_common import BOOL_OVERSHOOT_MM, box_at, rectangular_frustum


@dataclass(frozen=True)
class FistFigure:
    """Dimensions in millimetres."""

    # Socket interface: the tenon that drops into the pedestal.
    tenon_width: float = 30.0
    tenon_depth: float = 22.0
    tenon_height: float = 5.7

    # Wrist, flaring from the tenon up to the full body.
    wrist_height: float = 10.0

    # Body of the fist.
    mass_width: float = 40.0
    mass_depth: float = 30.0
    mass_height: float = 38.0

    # Curled fingers: grooves between them, cut into the front face.
    fingers: int = 4
    groove_width: float = 2.6
    groove_depth: float = 3.0
    groove_bottom_z: float = 33.0

    # Thumb, crossing the lower front.
    thumb_length: float = 26.0
    thumb_thickness: float = 9.0
    thumb_proud: float = 5.0
    thumb_embed: float = 8.0
    thumb_angle_deg: float = 18.0
    thumb_center_x: float = -5.0
    thumb_center_z: float = 24.5

    # Pinky, rising out of the outermost finger column.
    pinky_width: float = 9.0
    pinky_depth: float = 9.0
    pinky_height: float = 26.0
    pinky_tip_height: float = 3.0
    pinky_tip_taper: float = 2.5
    pinky_lean_deg: float = 5.0

    @property
    def mass_bottom_z(self) -> float:
        return self.tenon_height + self.wrist_height

    @property
    def mass_top_z(self) -> float:
        return self.mass_bottom_z + self.mass_height

    @property
    def top_z(self) -> float:
        return self.mass_top_z + self.pinky_height

    @property
    def finger_boundaries_x(self) -> list[float]:
        """X of the grooves that separate the finger columns."""
        step = self.mass_width / self.fingers
        return [-self.mass_width / 2 + index * step for index in range(1, self.fingers)]

    @property
    def pinky_center_x(self) -> float:
        """Middle of the outermost finger column."""
        return (self.finger_boundaries_x[-1] + self.mass_width / 2) / 2

    @property
    def front_y(self) -> float:
        return -self.mass_depth / 2


def _tenon(spec: FistFigure) -> trimesh.Trimesh:
    """Overlaps the wrist flare so the union has no coplanar faces."""
    return box_at(
        (spec.tenon_width, spec.tenon_depth, spec.tenon_height + 1.0),
        (0.0, 0.0, (spec.tenon_height + 1.0) / 2),
    )


def _wrist(spec: FistFigure) -> trimesh.Trimesh:
    return rectangular_frustum(
        (spec.tenon_width, spec.tenon_depth),
        (spec.mass_width, spec.mass_depth),
        spec.wrist_height,
        base_z=spec.tenon_height,
    )


def _mass(spec: FistFigure) -> trimesh.Trimesh:
    return box_at(
        (spec.mass_width, spec.mass_depth, spec.mass_height),
        (0.0, 0.0, spec.mass_bottom_z + spec.mass_height / 2),
    )


def _finger_grooves(spec: FistFigure) -> list[trimesh.Trimesh]:
    """Three slots between the four fingers, cutting the front face and the top edge."""
    height = spec.mass_top_z - spec.groove_bottom_z + BOOL_OVERSHOOT_MM
    center_y = spec.front_y + spec.groove_depth / 2
    center_z = spec.mass_top_z + BOOL_OVERSHOOT_MM - height / 2
    return [
        box_at((spec.groove_width, spec.groove_depth, height), (x, center_y, center_z))
        for x in spec.finger_boundaries_x
    ]


def _thumb(spec: FistFigure) -> trimesh.Trimesh:
    depth = spec.thumb_proud + spec.thumb_embed
    center_y = spec.front_y - spec.thumb_proud + depth / 2
    thumb = box_at(
        (spec.thumb_length, depth, spec.thumb_thickness),
        (spec.thumb_center_x, center_y, spec.thumb_center_z),
    )
    pivot = [spec.thumb_center_x, center_y, spec.thumb_center_z]
    thumb.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(spec.thumb_angle_deg), [0.0, 1.0, 0.0], point=pivot
        )
    )
    return thumb


def _pinky(spec: FistFigure) -> trimesh.Trimesh:
    """A tapered column rising from its finger column, leaning slightly outward."""
    base_z = spec.mass_top_z - 2.0  # sunk into the body for a clean union
    shaft_height = spec.pinky_height - spec.pinky_tip_height + 2.0
    shaft = box_at(
        (spec.pinky_width, spec.pinky_depth, shaft_height),
        (spec.pinky_center_x, 0.0, base_z + shaft_height / 2),
    )
    tip = rectangular_frustum(
        (spec.pinky_width, spec.pinky_depth),
        (
            spec.pinky_width - spec.pinky_tip_taper,
            spec.pinky_depth - spec.pinky_tip_taper,
        ),
        spec.pinky_tip_height,
        base_z=spec.mass_top_z + spec.pinky_height - spec.pinky_tip_height,
    )
    tip.apply_translation([spec.pinky_center_x, 0.0, 0.0])
    pinky = trimesh.boolean.union([shaft, tip], engine="manifold")

    pinky.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(spec.pinky_lean_deg),
            [0.0, 1.0, 0.0],
            point=[spec.pinky_center_x, 0.0, spec.mass_top_z],
        )
    )
    return pinky


def build_fist(spec: FistFigure | None = None) -> trimesh.Trimesh:
    """The complete figure, with its origin at the bottom of the tenon."""
    spec = spec or FistFigure()
    body = trimesh.boolean.union(
        [_tenon(spec), _wrist(spec), _mass(spec), _thumb(spec), _pinky(spec)],
        engine="manifold",
    )
    return trimesh.boolean.difference([body, *_finger_grooves(spec)], engine="manifold")
