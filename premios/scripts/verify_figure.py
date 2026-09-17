#!/usr/bin/env python3
"""Verify every award figure, and render them side by side for a human to judge.

Two models are verified with the same code, so their differences are real
differences and not differences in how hard they were measured:

  * `figura-punyo` - the first, plain geometric fist
  * `figura-punyo-cubista` - the second, faceted, cubist fist

Geometric checks (the machine decides these):

  1. One watertight solid with positive volume.
  2. **Three notches in the front profile**, found as peaks in the front-most Y
     as a function of X. Three notches means four finger columns. Counting peaks
     works for square grooves and wedge grooves alike, and does not rely on
     slicing exactly inside a groove.
  3. **The right number of knuckles above the fist.** This is the check that
     matters most for reading the raised finger as the *pinky*: at a height
     clear of the body there must be one separate region per knuckle plus the
     pinky, and every knuckle must sit on the thumb side of the pinky column.
     Three knuckles and then a raised finger makes it the fourth finger.
  4. The pinky stands alone above everything, close to its nominal section,
     thick enough and high enough.
  5. The thumb protrudes past the front face.
  6. The tenon fits the pedestal socket, with the socket floor still clearing
     the hollow cavity underneath.
  7. The render convention puts the pinky up and on the right, and the preview
     actually drew something.

Aesthetic judgement is deliberately left to the human looking at the PNG.

Usage:  .venv/bin/python scripts/verify_figure.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import shapely
import trimesh
from matplotlib.collections import PolyCollection
from scipy.signal import find_peaks
from shapely.geometry import LineString, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_premios import Pedestal, pedestal_cavity  # noqa: E402
from fist_cubist import FistCubist, build_fist_cubist  # noqa: E402
from fist_figure import FistFigure, build_fist  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "out"
PREVIEW_DIR = OUT_DIR / "previews"

# Shared view convention: camera on -Y, screen is (X, Z), light upper left.
SCREEN_AXES = (0, 2)
DEPTH_AXIS = 1
LIGHT = np.array([-0.40, -0.70, 0.59])

MIN_PINKY_MM = 7.0
MIN_PINKY_RISE_MM = 20.0
MIN_NOTCH_PROMINENCE_MM = 1.2
MIN_TENON_CLEARANCE_MM = 0.4
MIN_SOCKET_FLOOR_MM = 3.0
PROFILE_EDGE_MARGIN_MM = 6.0


@dataclass
class Model:
    name: str
    slug: str
    spec: FistFigure | FistCubist
    mesh: trimesh.Trimesh


def build_models() -> list[Model]:
    plain, plain_spec = build_fist(), FistFigure()
    cubist, cubist_spec = build_fist_cubist(), FistCubist()
    return [
        Model("plain geometric", "figura-punyo", plain_spec, plain),
        Model("cubist faceted", "figura-punyo-cubista", cubist_spec, cubist),
    ]


# ------------------------------------------------------------------ geometry


def _coords(geometry: shapely.Geometry) -> list[tuple[float, float]]:
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Point":
        return [(geometry.x, geometry.y)]
    if hasattr(geometry, "geoms"):
        out: list[tuple[float, float]] = []
        for part in geometry.geoms:
            out.extend(_coords(part))
        return out
    return [(x, y) for x, y in geometry.coords]


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


def parts(geometry: shapely.Geometry) -> list[shapely.Geometry]:
    if geometry.is_empty:
        return []
    return list(geometry.geoms) if hasattr(geometry, "geoms") else [geometry]


def front_profile(mesh: trimesh.Trimesh, spec, z: float) -> tuple[np.ndarray, np.ndarray]:
    """Front-most Y as a function of X, across the middle of the finger panels."""
    section = cross_section(mesh, z)
    half = spec.mass_width / 2 - PROFILE_EDGE_MARGIN_MM
    xs = np.linspace(-half, half, 401)
    ys = np.full(xs.shape, np.nan)
    for index, x in enumerate(xs):
        clipped = section.intersection(LineString([(x, -500.0), (x, 500.0)]))
        points = _coords(clipped)
        if points:
            ys[index] = min(y for _, y in points)
    return xs, ys


def check_mesh(model: Model) -> bool:
    print(f"check 1: {model.name} is one printable solid")
    mesh = model.mesh
    checks = {
        "watertight": mesh.is_watertight,
        "single body": mesh.body_count == 1,
        "positive volume": mesh.volume > 0,
        "winding consistent": mesh.is_winding_consistent,
    }
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print(
        f"  model {mesh.volume / 1000:.2f} cm3, {len(mesh.faces)} faces, "
        f"bbox {np.round(mesh.extents, 1).tolist()} mm"
    )
    return all(checks.values())


def check_fingers(model: Model) -> bool:
    spec = model.spec
    z = spec.groove_bottom_z + 5.0
    xs, ys = front_profile(model.mesh, spec, z)
    print(f"\ncheck 2: {model.name} reads as four fingers (profile at z={z:.0f})")
    if np.isnan(ys).any():
        print("  [FAIL] profile has gaps, cannot count notches")
        return False
    peaks, properties = find_peaks(ys, prominence=MIN_NOTCH_PROMINENCE_MM)
    expected = spec.fingers - 1
    checks = {
        f"exactly {expected} notches in the front profile (found {len(peaks)})": len(peaks) == expected,
        "notches are separated along X": len(peaks) < 2
        or float(np.min(np.diff(xs[peaks]))) > 4.0,
    }
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print(
        f"    notch x positions {np.round(xs[peaks], 1).tolist()} mm, "
        f"depths {np.round(properties.get('prominences', []), 2).tolist()} mm"
    )
    return all(checks.values())


def check_knuckles(model: Model) -> bool:
    """Three knuckles beside one raised finger is what names it the pinky."""
    spec = model.spec
    z = spec.mass_top_z + 2.0
    regions = parts(cross_section(model.mesh, z))
    centres = sorted((region.bounds[0] + region.bounds[2]) / 2 for region in regions)
    print(f"\ncheck 3: {model.name} knuckles frame the raised finger (z={z:.1f})")

    expected = spec.knuckle_count
    if expected == 0:
        print(f"  [PASS] this version has no knuckle blocks; {len(regions)} region above")
        return len(regions) == 1

    knuckles = [centre for centre in centres if centre < spec.pinky_column[0]]
    raised = [centre for centre in centres if centre >= spec.pinky_column[0]]
    checks = {
        f"{expected} knuckles plus the pinky above the fist": len(regions) == expected + 1,
        f"every knuckle is on the thumb side of the pinky ({len(knuckles)})": len(knuckles) == expected,
        "exactly one raised finger beyond them": len(raised) == 1,
    }
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print(
        f"    region centres at x = {np.round(centres, 1).tolist()} mm "
        f"(pinky column starts at {spec.pinky_column[0]:.1f})"
    )
    return all(checks.values())


def check_pinky(model: Model) -> bool:
    spec = model.spec
    z = spec.mass_top_z + 6.0
    region = cross_section(model.mesh, z)
    regions = parts(region)
    area = region.area
    nominal = spec.nominal_pinky_area
    centre_x = (region.bounds[0] + region.bounds[2]) / 2 if regions else 0.0
    thumb_proud = spec.front_y - model.mesh.bounds[0][1]

    print(f"\ncheck 4: {model.name} pinky stands alone, thick and high")
    checks = {
        "one region above the fist": len(regions) == 1,
        f"section within 25% of nominal ({area:.0f} vs {nominal:.0f} mm2)": abs(
            area - nominal
        )
        <= 0.25 * nominal,
        "pinky is the outer column": centre_x > spec.mass_width / 4,
        f"thick enough (>= {MIN_PINKY_MM} mm)": spec.pinky_width >= MIN_PINKY_MM,
        f"rises >= {MIN_PINKY_RISE_MM} mm": spec.pinky_height >= MIN_PINKY_RISE_MM,
        f"thumb protrudes ({thumb_proud:.1f} mm)": thumb_proud > 2.0,
    }
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print(f"    pinky section {area:.1f} mm2 at x={centre_x:.1f}, rises {spec.pinky_height:.0f} mm")
    return all(checks.values())


def check_interface(model: Model) -> bool:
    spec = model.spec
    pedestal = Pedestal()
    cavity = pedestal_cavity(pedestal)
    clearance = min(
        pedestal.socket_width - spec.tenon_width,
        pedestal.socket_depth - spec.tenon_depth,
    )
    floor_material = (
        pedestal.socket_floor_z - cavity.bounds[1][2] if cavity is not None else pedestal.height
    )
    print(f"\ncheck 5: {model.name} fits the pedestal")
    checks = {
        f"tenon clearance >= {MIN_TENON_CLEARANCE_MM} mm ({clearance:.2f})": clearance
        >= MIN_TENON_CLEARANCE_MM,
        "tenon shorter than the socket": spec.tenon_height < pedestal.socket_recess,
        f"socket floor material >= {MIN_SOCKET_FLOOR_MM} mm ({floor_material:.1f})": floor_material
        >= MIN_SOCKET_FLOOR_MM,
        "figure base sits on the socket floor": abs(model.mesh.bounds[0][2]) < 1e-6,
    }
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print(
        f"    award height "
        f"{pedestal.height + spec.top_z - spec.tenon_height:.0f} mm "
        f"(pedestal {pedestal.height:.0f} + figure {spec.top_z - spec.tenon_height:.0f} visible)"
    )
    return all(checks.values())


def check_view_convention(model: Model) -> bool:
    print(f"\ncheck 6: {model.name} render convention is unambiguous")
    vertices = model.mesh.vertices
    top = vertices[np.argmax(vertices[:, 2])]
    checks = {
        "highest point is the pinky tip, on the right": top[0] > 0.0,
        "highest point is at the nominal tip height": abs(top[2] - model.spec.top_z) < 2.5,
        "the pinky tip is not hidden behind the fist": top[1] < model.spec.mass_depth / 2,
    }
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print(f"    top vertex {np.round(top, 1).tolist()} vs nominal tip z={model.spec.top_z:.1f}")
    return all(checks.values())


# ------------------------------------------------------------------ rendering


def hero_matrix() -> np.ndarray:
    """Turn the fist so the front face and the pinky are both visible."""
    turn = trimesh.transformations.rotation_matrix(np.radians(-28.0), [0.0, 0.0, 1.0])
    tilt = trimesh.transformations.rotation_matrix(np.radians(-12.0), [1.0, 0.0, 0.0])
    return tilt @ turn


def render(
    ax: plt.Axes,
    mesh: trimesh.Trimesh,
    title: str,
    view: np.ndarray,
    limits: tuple[float, float, float, float] | None = None,
) -> None:
    viewed = mesh.copy()
    viewed.apply_transform(view)

    triangles = viewed.vertices[viewed.faces]
    centres = triangles.mean(axis=1)
    order = np.argsort(-centres[:, DEPTH_AXIS])  # far to near

    lambert = np.clip(viewed.face_normals @ LIGHT, 0.0, 1.0)
    palette = plt.get_cmap("bone")(0.15 + 0.62 * (0.34 + 0.66 * lambert))[:, :3]

    ax.add_collection(
        PolyCollection(
            triangles[order][:, :, list(SCREEN_AXES)],
            facecolors=palette[order],
            edgecolors=(0.18, 0.18, 0.20),
            linewidths=0.18,
        )
    )
    ax.autoscale_view()
    if limits is not None:
        ax.set_xlim(limits[0], limits[1])
        ax.set_ylim(limits[2], limits[3])
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=8, color="#333")


def render_comparison(models: list[Model]) -> Path:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    identity = np.eye(4)
    fig, axes = plt.subplots(len(models), 3, figsize=(13, 4 * len(models)))
    if len(models) == 1:
        axes = np.array([axes])

    for row, model in enumerate(models):
        spec = model.spec
        detail = (
            -spec.mass_width * 0.62,
            spec.mass_width * 0.62,
            spec.mass_top_z - 14.0,
            spec.top_z + 4.0,
        )
        panels = [
            ("front full", identity, None),
            ("hero (turned 28 deg, tilted 12)", hero_matrix(), None),
            ("front detail: knuckles and pinky", identity, detail),
        ]
        for column, (label, view, limits) in enumerate(panels):
            render(axes[row][column], model.mesh, f"{model.slug} - {label}", view, limits)
        axes[row][0].set_ylabel(model.name, fontsize=9)

    fig.suptitle(
        "ConRol award figure - the two candidate versions, orthographic, same scale",
        fontsize=11,
    )
    fig.tight_layout()
    target = PREVIEW_DIR / "figura-comparativa.png"
    fig.savefig(target, dpi=150)
    plt.close(fig)
    return target


def check_render(target: Path, rows: int) -> bool:
    """A blank or flat-shaded render would pass silently otherwise."""
    print("\ncheck 7: the comparison sheet actually rendered")
    grey = plt.imread(target)[:, :, :3].mean(axis=2)
    inked = grey < 0.985
    levels = len(np.unique(np.round(grey[inked], 2)))
    fraction = float(inked.mean())
    height = grey.shape[0]
    bands = [inked[r * height // rows : (r + 1) * height // rows] for r in range(rows)]
    checks = {
        f"has ink ({fraction * 100:.1f}% of the image)": 0.05 < fraction < 0.90,
        f"shading varies ({levels} grey levels)": levels > 20,
        "every model row drew something": all(band.any() for band in bands),
    }
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    return all(checks.values())


def main() -> int:
    models = build_models()
    results = []
    for model in models:
        print("=" * 72)
        results.append(check_mesh(model))
        results.append(check_fingers(model))
        results.append(check_knuckles(model))
        results.append(check_pinky(model))
        results.append(check_interface(model))
        results.append(check_view_convention(model))

    target = render_comparison(models)
    results.append(check_render(target, len(models)))

    print("\n" + "=" * 72)
    print(f"comparison sheet: {target}  <- open this and pick one")
    passed = all(results)
    print(f"result: {'all geometry checks passed' if passed else 'CHECKS FAILED'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
