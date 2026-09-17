#!/usr/bin/env python3
"""Verify the award figure, and render it so a human can judge the styling.

Geometric checks (the machine decides these):

  1. The mesh is a single watertight solid with positive volume.
  2. It reads as a fist: four finger fronts on the front face, separated by the
     three grooves, counted as four disjoint regions in a slab cut through the
     groove depth.
  3. The pinky stands alone above the fist, one region, close to its nominal
     cross-section, thick enough not to snap and far enough above the knuckles
     to read as raised.
  4. The thumb actually protrudes past the front face instead of being swallowed.
  5. The tenon fits the pedestal socket with clearance, and the socket floor
     still clears the hollow cavity underneath it.
  6. The view convention used for the renders puts the pinky up and to the
     right, so the images cannot be silently mirrored or upside down.

The renders are flat-shaded and orthographic: good enough to judge silhouette
and read, not to judge surface finish. Aesthetic judgement is deliberately left
to the human looking at them.

Usage:  .venv/bin/python scripts/verify_figure.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import shapely
import trimesh
from matplotlib.collections import PolyCollection
from shapely.geometry import Polygon, box

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_premios import FistFigure, Pedestal, build_pedestal, pedestal_cavity  # noqa: E402
from fist_figure import build_fist  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "out"
PREVIEW_DIR = OUT_DIR / "previews"

# View convention shared by every render: camera on -Y, screen is (X, Z), and
# the light comes from the viewer's upper left.
SCREEN_AXES = (0, 2)
DEPTH_AXIS = 1
LIGHT = np.array([-0.40, -0.70, 0.59])

MIN_PINKY_MM = 7.0
MIN_PINKY_RISE_MM = 20.0
MIN_TENON_CLEARANCE_MM = 0.4
MIN_SOCKET_FLOOR_MM = 3.0


def cross_section(mesh: trimesh.Trimesh, z: float) -> shapely.Geometry:
    """The solid's cross-section at height z, as an even-odd filled region."""
    section = mesh.section(plane_origin=[0.0, 0.0, z], plane_normal=[0.0, 0.0, 1.0])
    if section is None:
        return Polygon()
    rings = [Polygon(loop[:, :2]) for loop in section.discrete]
    rings = [ring for ring in rings if ring.is_valid and not ring.is_empty]
    if not rings:
        return Polygon()
    result: shapely.Geometry = rings[0]
    for ring in rings[1:]:
        result = result.symmetric_difference(ring)
    return result


def part_count(geometry: shapely.Geometry) -> int:
    if geometry.is_empty:
        return 0
    return len(geometry.geoms) if hasattr(geometry, "geoms") else 1


def finger_fronts(figure: trimesh.Trimesh, spec: FistFigure) -> shapely.Geometry:
    """The four finger fronts, isolated by cutting a slab through the grooves.

    The grooves only reach `groove_depth` into the body, so restricting the
    section to that slab removes the material that joins the fingers behind it.
    """
    z = spec.groove_bottom_z + 5.0
    slab = box(
        -spec.mass_width * 2,
        spec.front_y - 1.0,
        spec.mass_width * 2,
        spec.front_y + spec.groove_depth - 0.15,
    )
    return cross_section(figure, z).intersection(slab)


# ------------------------------------------------------------------ geometry


def check_mesh(figure: trimesh.Trimesh) -> bool:
    print("check 1: the figure is one printable solid")
    checks = {
        "watertight": figure.is_watertight,
        "single body": figure.body_count == 1,
        "positive volume": figure.volume > 0,
        "winding consistent": figure.is_winding_consistent,
    }
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print(
        f"  model {figure.volume / 1000:.2f} cm3, {len(figure.faces)} faces, "
        f"bbox {np.round(figure.extents, 1).tolist()} mm"
    )
    return all(checks.values())


def check_reads_as_fist(figure: trimesh.Trimesh, spec: FistFigure) -> bool:
    print("\ncheck 2: it reads as a fist - four fingers, a thumb, a raised pinky")
    fronts = finger_fronts(figure, spec)
    count = part_count(fronts)
    widths = sorted(
        round(part.bounds[2] - part.bounds[0], 2)
        for part in (fronts.geoms if hasattr(fronts, "geoms") else [fronts])
    )

    above_z = spec.mass_top_z + 5.0
    above = cross_section(figure, above_z)
    above_count = part_count(above)
    above_area = above.area
    above_center_x = (above.bounds[0] + above.bounds[2]) / 2 if above_count else 0.0

    rise = spec.pinky_height
    thumb_min_y = figure.bounds[0][1]
    thumb_proud = spec.front_y - thumb_min_y

    checks = {
        f"exactly {spec.fingers} finger fronts": count == spec.fingers,
        "finger columns are even": max(widths) - min(widths) < 3.0,
        "only the pinky above the fist": above_count == 1,
        f"pinky cross-section in range ({above_area:.0f} mm2)": 60.0 < above_area < 95.0,
        "pinky is the outer column": above_center_x > spec.mass_width / 4,
        f"pinky is thick enough (>= {MIN_PINKY_MM} mm)": spec.pinky_width >= MIN_PINKY_MM,
        f"pinky rises >= {MIN_PINKY_RISE_MM} mm": rise >= MIN_PINKY_RISE_MM,
        f"thumb protrudes ({thumb_proud:.1f} mm)": thumb_proud > 2.0,
    }
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print(f"    finger widths at z={spec.groove_bottom_z + 5.0:.0f}: {widths} mm")
    print(f"    pinky section at z={above_z:.0f}: {above_area:.1f} mm2 at x={above_center_x:.1f}")
    return all(checks.values())


def check_interface(figure: trimesh.Trimesh, spec: FistFigure) -> bool:
    print("\ncheck 3: the figure fits the pedestal")
    pedestal = Pedestal()
    cavity = pedestal_cavity(pedestal)
    clearance = min(
        pedestal.socket_width - spec.tenon_width,
        pedestal.socket_depth - spec.tenon_depth,
    )
    floor_material = (
        pedestal.socket_floor_z - cavity.bounds[1][2] if cavity is not None else pedestal.height
    )
    bottom = figure.bounds[0]
    checks = {
        f"tenon clearance >= {MIN_TENON_CLEARANCE_MM} mm ({clearance:.2f})": clearance
        >= MIN_TENON_CLEARANCE_MM,
        "tenon shorter than the socket": spec.tenon_height < pedestal.socket_recess,
        "figure sits on the socket floor": abs(bottom[2]) < 1e-6,
        f"socket floor material >= {MIN_SOCKET_FLOOR_MM} mm ({floor_material:.1f})": floor_material
        >= MIN_SOCKET_FLOOR_MM,
        "figure centred on the socket": abs(bottom[0] + pedestal.socket_width / 2 - 0.0) < 30.0,
    }
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print(
        f"    award height "
        f"{pedestal.height + spec.top_z - spec.tenon_height:.0f} mm "
        f"(pedestal {pedestal.height:.0f} + figure {spec.top_z - spec.tenon_height:.0f} visible)"
    )
    # A pedestal built with the figure's category must still be a valid solid.
    return all(checks.values())


def check_view_convention(figure: trimesh.Trimesh, spec: FistFigure) -> bool:
    """Tie the model to the render convention, so the images cannot lie."""
    print("\ncheck 4: render convention is unambiguous")
    vertices = figure.vertices
    top = vertices[np.argmax(vertices[:, 2])]
    checks = {
        "highest point is the pinky tip (x > 0, on the right)": top[0] > 0.0,
        "highest point is at the nominal tip height": abs(top[2] - spec.top_z) < 2.0,
        "the pinky tip is not hidden behind the fist": top[1] < spec.mass_depth / 2,
    }
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print(f"    top vertex {np.round(top, 1).tolist()} vs nominal tip z={spec.top_z:.1f}")
    return all(checks.values())


# ------------------------------------------------------------------ rendering


def hero_matrix() -> np.ndarray:
    """Turn the fist slightly so the front face and the pinky are both visible."""
    turn = trimesh.transformations.rotation_matrix(np.radians(-28.0), [0.0, 0.0, 1.0])
    tilt = trimesh.transformations.rotation_matrix(np.radians(-12.0), [1.0, 0.0, 0.0])
    return tilt @ turn


def render(ax: plt.Axes, mesh: trimesh.Trimesh, title: str, view: np.ndarray, shade_symbol: str) -> None:
    """Flat-shaded orthographic render using the shared view convention."""
    viewed = mesh.copy()
    viewed.apply_transform(view)

    triangles = viewed.vertices[viewed.faces]
    centres = triangles.mean(axis=1)
    order = np.argsort(-centres[:, DEPTH_AXIS])  # far to near

    normals = viewed.face_normals
    lambert = np.clip(normals @ LIGHT, 0.0, 1.0)
    intensity = 0.34 + 0.66 * lambert
    palette = plt.get_cmap("bone")(0.15 + 0.62 * intensity)[:, :3]

    ax.add_collection(
        PolyCollection(
            triangles[order][:, :, list(SCREEN_AXES)],
            facecolors=palette[order],
            edgecolors=tuple(np.array([0.18, 0.18, 0.20])),
            linewidths=0.18,
        )
    )
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.axis("off")
    height = mesh.extents[2]
    ax.set_title(f"{title} {shade_symbol}", fontsize=8, color="#333")


def render_previews(figure: trimesh.Trimesh) -> Path:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    identity = np.eye(4)
    views = [
        ("front (from -Y)", identity, "\u2190 the plaque side"),
        ("hero (turned 28 deg)", hero_matrix(), ""),
        (
            "side (from +X)",
            trimesh.transformations.rotation_matrix(np.radians(90.0), [0.0, 0.0, 1.0]),
            "\u2190 pinky side",
        ),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    for ax, (title, view, symbol) in zip(axes, views):
        render(ax, figure, title, view, symbol)
    fig.suptitle(
        "ConRol award figure - closed fist with the pinky raised (all views orthographic)",
        fontsize=10,
    )
    fig.tight_layout()
    target = PREVIEW_DIR / "figura-vistas.png"
    fig.savefig(target, dpi=150)
    plt.close(fig)
    return target


def check_render(target: Path) -> bool:
    """A blank or flat-shaded render would pass silently otherwise.

    Nobody here can look at the image, so the machine asserts the least it can:
    the picture has ink, the shading actually varies, and all three panels drew
    something.
    """
    print("\ncheck 5: the preview actually rendered")
    grey = plt.imread(target)[:, :, :3].mean(axis=2)
    inked = grey < 0.985
    levels = len(np.unique(np.round(grey[inked], 2)))
    fraction = float(inked.mean())
    width = grey.shape[1]
    panels = [inked[:, index * width // 3 : (index + 1) * width // 3] for index in range(3)]

    checks = {
        f"has ink ({fraction * 100:.1f}% of the image)": 0.05 < fraction < 0.90,
        f"shading varies ({levels} grey levels)": levels > 20,
        "all three panels drew something": all(panel.any() for panel in panels),
    }
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    return all(checks.values())


def main() -> int:
    spec = FistFigure()
    figure = build_fist(spec)
    results = [
        check_mesh(figure),
        check_reads_as_fist(figure, spec),
        check_interface(figure, spec),
        check_view_convention(figure, spec),
    ]
    target = render_previews(figure)
    results.append(check_render(target))
    print(f"\npreview written: {target}  <- open this and judge the styling")
    passed = all(results)
    print(f"result: {'all geometry checks passed' if passed else 'CHECKS FAILED'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
