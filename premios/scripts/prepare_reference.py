#!/usr/bin/env python3
"""Prepare the reference sculpture as the basis for the ConRol award.

Takes `ref/mano-referencia.stl` (a hand with the little finger raised, standing
on a rectangular base), removes the plaque that is modelled into the base, and
rescales the whole thing to a 100 mm overall height with the origin at the
bottom centre.

Why the plaque has to be cut rather than deleted: it is not a separate solid.
It is a plate 40.6 x 10.0 mm standing 1.19 mm proud of the base's front face,
fused into the same watertight shell. Removing it therefore means cutting the
front face back to a plane, not deleting an object. A cutter limited to the
base's height range does that and leaves the hand untouched.

The cut plane is set a little *behind* the base's face on purpose. Cutting
exactly flush would be a coplanar boolean and would leave a hair-thin stub of
the plate behind; backing off by ~0.15 mm guarantees a clean flat face at the
cost of 0.15 mm of the base's depth.

Usage:  .venv/bin/python scripts/prepare_reference.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "ref" / "mano-referencia.stl"
OUT_DIR = REPO_ROOT / "out"

TARGET_HEIGHT_MM = 100.0
# Anything standing this far proud of a vertical face is a modelled feature.
PROUD_THRESHOLD_MM = 0.3
# How far behind the face to cut, so the boolean is never coplanar.
CUT_BACK_MM = 0.15
SCAN_COLUMNS = 110
SCAN_ROWS = 26


def model_scale(mesh: trimesh.Trimesh) -> float:
    """Millimetres per model unit, normalised so the height reads as 200 mm.

    The STL carries no units. Reporting at a 200 mm reference height keeps the
    intermediate numbers comparable with the analysis this was built from; the
    final export is rescaled to TARGET_HEIGHT_MM regardless.
    """
    return 200.0 / float(mesh.extents[2])


def base_top_z(mesh: trimesh.Trimesh) -> float:
    """Where the wide base ends and the hand begins: the biggest drop in area."""
    low, high = mesh.bounds
    heights = np.linspace(low[2], low[2] + 0.25 * (high[2] - low[2]), 240)
    areas = []
    for z in heights:
        section = mesh.section(plane_origin=[0.0, 0.0, z], plane_normal=[0.0, 0.0, 1.0])
        total = 0.0
        if section is not None:
            for loop in section.discrete:
                x, y = loop[:, 0], loop[:, 1]
                total += abs(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y) / 2)
        areas.append(total)
    step = int(np.argmin(np.diff(areas)))
    return float(heights[step + 1])


def face_relief(
    mesh: trimesh.Trimesh, axis: int, sign: int, z_low: float, z_high: float, scale: float
) -> tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    """How far each patch of a vertical face stands proud of that face's plane.

    Rays are fired at the face from outside and the first hit is kept, which
    gives the surface's own coordinate rather than the bounding box's.
    """
    low, high = mesh.bounds
    other = 1 - axis
    start = high[axis] + 0.5 if sign > 0 else low[axis] - 0.5
    direction = -1.0 if sign > 0 else 1.0

    along = np.linspace(low[other] + 0.01, high[other] - 0.01, SCAN_COLUMNS)
    heights = np.linspace(z_low + 0.002, z_high - 0.002, SCAN_ROWS)
    grid_a, grid_z = np.meshgrid(along, heights, indexing="ij")

    origins = np.zeros((grid_a.size, 3))
    origins[:, axis] = start
    origins[:, other] = grid_a.ravel()
    origins[:, 2] = grid_z.ravel()
    directions = np.zeros((grid_a.size, 3))
    directions[:, axis] = direction

    locations, ray_index, _ = mesh.ray.intersects_location(origins, directions)
    hit = np.full(grid_a.size, np.nan)
    for ray, value in zip(ray_index, locations[:, axis]):
        if np.isnan(hit[ray]) or (value > hit[ray] if sign > 0 else value < hit[ray]):
            hit[ray] = value
    hit = (hit * scale).reshape(grid_a.shape)

    plane = float(np.nanmedian(hit))
    proud = (plane - hit) if sign < 0 else (hit - plane)
    return plane, proud, along * scale, heights


def plaque_cutters(mesh: trimesh.Trimesh, z_low: float, z_high: float, scale: float) -> list[trimesh.Trimesh]:
    """One cutter per vertical face that carries a modelled plaque."""
    low, high = mesh.bounds
    span = high - low
    cutters = []
    for axis, sign, name in (
        (1, -1, "front"),
        (1, 1, "back"),
        (0, -1, "left"),
        (0, 1, "right"),
    ):
        plane, proud, _, _ = face_relief(mesh, axis, sign, z_low, z_high, scale)
        peak = float(np.nanmax(proud))
        covered = 100.0 * np.nansum(proud > PROUD_THRESHOLD_MM) / proud.size
        print(f"  {name:6s} face: plane at {plane:+.2f} mm, relief {peak:.2f} mm, {covered:.0f}% covered")
        if peak <= PROUD_THRESHOLD_MM:
            continue

        # Cut back to just INSIDE the face plane. `outward` is the direction the
        # face looks in, so the cutter spans from far outside inwards to a plane
        # CUT_BACK_MM behind the face. Cutting flush would be coplanar; cutting
        # in front of the face leaves a lip of the plate behind, which is what
        # the first attempt did (0.15 mm of plaque survived).
        outward = float(sign)
        plane_model = plane / scale
        near = plane_model - outward * (CUT_BACK_MM / scale)
        far = plane_model + outward * 10.0
        cutter = trimesh.creation.box(extents=np.abs(span) + 2.0)
        size = cutter.extents.copy()
        size[axis] = abs(far - near)
        size[2] = z_high - z_low + 0.02
        cutter = trimesh.creation.box(extents=size)
        centre = (low + high) / 2.0
        centre[axis] = (near + far) / 2.0
        centre[2] = (z_low + z_high) / 2.0
        cutter.apply_translation(centre)
        print(f"    -> cutting the {name} face back to {plane_model * scale:+.2f} mm over z {z_low * scale:.1f}..{z_high * scale:.1f}")
        cutters.append(cutter)
    return cutters


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"reference model not found: {SOURCE}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    mesh = trimesh.load(SOURCE, force="mesh")
    if not isinstance(mesh, trimesh.Trimesh):
        raise SystemExit("the reference did not load as a single mesh")
    scale = model_scale(mesh)
    low, high = mesh.bounds
    top = base_top_z(mesh)
    print(f"reference: {len(mesh.faces)} faces, {mesh.body_count} body, watertight={mesh.is_watertight}")
    print(f"  height {mesh.extents[2]:.4f} units -> {mesh.extents[2] * scale:.1f} mm at the reporting scale")
    print(f"  base ends at {(top - low[2]) * scale:.1f} mm above the bottom\n")

    print("scanning the base's vertical faces:")
    cutters = plaque_cutters(mesh, low[2] + 0.001, top - 0.005, scale)
    if not cutters:
        print("\nno modelled plaque found; nothing to remove")
        cleaned = mesh
    else:
        cleaned = trimesh.boolean.difference([mesh, *cutters], engine="manifold")
        print(f"\nafter the cut: {len(cleaned.faces)} faces, watertight={cleaned.is_watertight}, bodies={cleaned.body_count}")

    print("re-checking the front face:")
    plane, proud, _, _ = face_relief(cleaned, 1, -1, low[2] + 0.001, top - 0.005, scale)
    print(f"  relief now {float(np.nanmax(proud)):.2f} mm (was 1.19 mm) -> flat to {float(np.nanmax(proud)):.2f} mm")

    # Rescale and re-origin: bottom on Z=0, bounding box centred in X and Y.
    factor = TARGET_HEIGHT_MM / float(cleaned.extents[2])
    cleaned.apply_scale(factor)
    cleaned.apply_translation(
        [
            -(cleaned.bounds[0][0] + cleaned.bounds[1][0]) / 2.0,
            -(cleaned.bounds[0][1] + cleaned.bounds[1][1]) / 2.0,
            -cleaned.bounds[0][2],
        ]
    )

    target = OUT_DIR / "figura-referencia-100mm.stl"
    cleaned.export(target)

    print(f"\nwritten {target}")
    print(f"  size {np.round(cleaned.extents, 2).tolist()} mm")
    print(f"  volume {cleaned.volume / 1000:.2f} cm3, faces {len(cleaned.faces)}")
    print(f"  watertight={cleaned.is_watertight}, bodies={cleaned.body_count}")
    print(f"  scale applied to the source: {factor:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
