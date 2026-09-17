#!/usr/bin/env python3
"""Shared solid-modelling helpers for the ConRol award parts.

Both the pedestal and the figure need the same primitives, and the build script
must not import the figure module in a circle, so they live here.
"""

from __future__ import annotations

import shapely
import trimesh
from shapely.geometry import MultiPolygon, Polygon

# Extra stock added to a cutter so the boolean never lands on a coplanar face.
BOOL_OVERSHOOT_MM = 0.6


def box_at(extents: tuple[float, float, float], center: tuple[float, float, float]) -> trimesh.Trimesh:
    """Axis-aligned box centred on `center`."""
    mesh = trimesh.creation.box(extents=list(extents))
    mesh.apply_translation(list(center))
    return mesh


def rectangular_frustum(
    bottom: tuple[float, float],
    top: tuple[float, float],
    height: float,
    base_z: float = 0.0,
) -> trimesh.Trimesh:
    """Rectangular frustum from Z=base_z up to Z=base_z+height, centred on X/Y.

    `bottom` and `top` are full widths in X and Y.
    """
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
    if base_z:
        mesh.apply_translation([0.0, 0.0, base_z])
    return mesh


def chamfered_rect(width: float, depth: float, chamfer: float) -> Polygon:
    """A rectangle with its four corners cut off, i.e. an octagon.

    The result is counter-clockwise so extrusion and scaling behave predictably.
    """
    half_w, half_d = width / 2, depth / 2
    cut = min(chamfer, half_w * 0.8, half_d * 0.8)
    return Polygon(
        [
            (half_w, -half_d + cut),
            (half_w, half_d - cut),
            (half_w - cut, half_d),
            (-half_w + cut, half_d),
            (-half_w, half_d - cut),
            (-half_w, -half_d + cut),
            (-half_w + cut, -half_d),
            (half_w - cut, -half_d),
        ]
    )


def extrude(geometry: shapely.Geometry, height: float, base_z: float = 0.0) -> trimesh.Trimesh:
    """Extrude a 2D geometry along +Z, starting at Z=base_z."""
    parts = geometry.geoms if isinstance(geometry, MultiPolygon) else [geometry]
    meshes = [
        trimesh.creation.extrude_polygon(part, height)
        for part in parts
        if isinstance(part, Polygon) and not part.is_empty
    ]
    if not meshes:
        raise ValueError("nothing to extrude")
    mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    if base_z:
        mesh.apply_translation([0.0, 0.0, base_z])
    return mesh
