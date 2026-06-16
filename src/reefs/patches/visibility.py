"""Target-region visibility helpers for patch camera selection."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median

from reefs.patches.artefacts import SparseImage, SparsePoint, SparseScene
from reefs.patches.bounds import PatchBounds


DEFAULT_TARGET_GRID_SIZE = 12
MAX_TARGET_SAMPLES = DEFAULT_TARGET_GRID_SIZE * DEFAULT_TARGET_GRID_SIZE


@dataclass(frozen=True)
class CameraIntrinsics:
    """Minimal pinhole intrinsics parsed from a COLMAP camera row."""

    camera_id: int
    model: str
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float


@dataclass(frozen=True)
class TargetSample:
    """One sampled point inside a patch target region."""

    sample_id: int
    xyz: tuple[float, float, float]
    role: str
    cell_id: str


def parse_camera_intrinsics(cameras_text: str) -> dict[int, CameraIntrinsics]:
    """Parse COLMAP camera rows into approximate pinhole intrinsics.

    Distortion coefficients are intentionally ignored because Feature 3 consumes
    COLMAP undistorted sparse models. The first focal/principal-point parameters
    are enough for target-region visibility scoring.
    """
    intrinsics: dict[int, CameraIntrinsics] = {}
    for line in cameras_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 5:
            continue
        try:
            camera_id = int(parts[0])
            model = parts[1].upper()
            width = int(parts[2])
            height = int(parts[3])
            params = [float(value) for value in parts[4:]]
        except ValueError:
            continue
        if model == "SIMPLE_PINHOLE" and len(params) >= 3:
            fx = fy = params[0]
            cx, cy = params[1], params[2]
        elif model in {"PINHOLE", "OPENCV", "OPENCV_FISHEYE", "FULL_OPENCV"} and len(params) >= 4:
            fx, fy, cx, cy = params[0], params[1], params[2], params[3]
        elif model in {"SIMPLE_RADIAL", "RADIAL", "SIMPLE_RADIAL_FISHEYE", "RADIAL_FISHEYE"} and len(params) >= 3:
            fx = fy = params[0]
            cx, cy = params[1], params[2]
        else:
            continue
        intrinsics[camera_id] = CameraIntrinsics(
            camera_id=camera_id,
            model=model,
            width=width,
            height=height,
            fx=fx,
            fy=fy,
            cx=cx,
            cy=cy,
        )
    return intrinsics


def _quaternion_to_rotation_matrix(qvec: tuple[float, float, float, float]) -> tuple[tuple[float, float, float], ...]:
    qw, qx, qy, qz = qvec
    return (
        (
            1.0 - 2.0 * qy * qy - 2.0 * qz * qz,
            2.0 * qx * qy - 2.0 * qz * qw,
            2.0 * qx * qz + 2.0 * qy * qw,
        ),
        (
            2.0 * qx * qy + 2.0 * qz * qw,
            1.0 - 2.0 * qx * qx - 2.0 * qz * qz,
            2.0 * qy * qz - 2.0 * qx * qw,
        ),
        (
            2.0 * qx * qz - 2.0 * qy * qw,
            2.0 * qy * qz + 2.0 * qx * qw,
            1.0 - 2.0 * qx * qx - 2.0 * qy * qy,
        ),
    )


def project_world_point(
    image: SparseImage,
    intrinsics: CameraIntrinsics,
    xyz: tuple[float, float, float],
) -> tuple[float, float, float] | None:
    """Project one world point into an image.

    Returns `(x, y, depth)` when the point is in front of the camera and inside
    image bounds; otherwise returns `None`.
    """
    rotation = _quaternion_to_rotation_matrix(image.qvec)
    camera_xyz = tuple(
        sum(rotation[row][axis] * xyz[axis] for axis in range(3)) + image.tvec[row]
        for row in range(3)
    )
    depth = camera_xyz[2]
    if not math.isfinite(depth) or depth <= 1e-9:
        return None
    x = intrinsics.fx * (camera_xyz[0] / depth) + intrinsics.cx
    y = intrinsics.fy * (camera_xyz[1] / depth) + intrinsics.cy
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    if x < 0.0 or y < 0.0 or x >= intrinsics.width or y >= intrinsics.height:
        return None
    return x, y, depth


def _robust_target_z(scene: SparseScene, bounds: PatchBounds, patch_points: list[SparsePoint]) -> float:
    z_values = [point.xyz[2] for point in patch_points]
    if not z_values:
        nearby = [
            point.xyz[2]
            for point in scene.points
            if bounds.min_x - bounds.buffer <= point.xyz[0] <= bounds.max_x + bounds.buffer
            and bounds.min_y - bounds.buffer <= point.xyz[1] <= bounds.max_y + bounds.buffer
        ]
        z_values = nearby
    if not z_values:
        z_values = [point.xyz[2] for point in scene.points]
    if not z_values:
        z_values = [image.center[2] for image in scene.images]
    if not z_values:
        return (bounds.min_z + bounds.max_z) / 2.0
    return float(median(z_values))


def build_target_samples(
    scene: SparseScene,
    bounds: PatchBounds,
    patch_points: list[SparsePoint],
    *,
    grid_size: int = DEFAULT_TARGET_GRID_SIZE,
) -> list[TargetSample]:
    """Build bounded target samples inside a patch."""
    grid_size = max(2, grid_size)
    target_z = _robust_target_z(scene, bounds, patch_points)
    samples: list[TargetSample] = []
    sample_id = 0
    for y_index in range(grid_size):
        y = bounds.min_y + ((y_index + 0.5) / grid_size) * bounds.height
        for x_index in range(grid_size):
            x = bounds.min_x + ((x_index + 0.5) / grid_size) * bounds.width
            role = "boundary" if bounds.is_boundary_xy(x, y) else "body"
            samples.append(
                TargetSample(
                    sample_id=sample_id,
                    xyz=(x, y, target_z),
                    role=role,
                    cell_id=f"{x_index}:{y_index}",
                )
            )
            sample_id += 1
            if len(samples) >= MAX_TARGET_SAMPLES:
                return samples
    return samples


def sparse_point_density_weights(points: list[SparsePoint], bounds: PatchBounds, *, grid_size: int = 10) -> dict[int, float]:
    """Return simple inverse-sqrt cell-density weights for sparse points."""
    grid_size = max(1, grid_size)
    if not points:
        return {}
    cell_by_point: dict[int, tuple[int, int]] = {}
    counts: dict[tuple[int, int], int] = {}
    width = max(bounds.width, 1e-9)
    height = max(bounds.height, 1e-9)
    for point in points:
        x_index = min(grid_size - 1, max(0, int(((point.xyz[0] - bounds.min_x) / width) * grid_size)))
        y_index = min(grid_size - 1, max(0, int(((point.xyz[1] - bounds.min_y) / height) * grid_size)))
        cell = (x_index, y_index)
        cell_by_point[point.point_id] = cell
        counts[cell] = counts.get(cell, 0) + 1
    return {
        point_id: 1.0 / math.sqrt(float(counts[cell_by_point[point_id]]))
        for point_id in cell_by_point
    }


def local_position_cell(image: SparseImage, bounds: PatchBounds, *, grid_size: int = 10) -> str | None:
    """Return the coarse local acquisition cell for a camera centre."""
    if not bounds.contains_xy(image.center[0], image.center[1]):
        return None
    width = max(bounds.width, 1e-9)
    height = max(bounds.height, 1e-9)
    x_index = min(grid_size - 1, max(0, int(((image.center[0] - bounds.min_x) / width) * grid_size)))
    y_index = min(grid_size - 1, max(0, int(((image.center[1] - bounds.min_y) / height) * grid_size)))
    return f"{x_index}:{y_index}"
