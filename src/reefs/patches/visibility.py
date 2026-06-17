"""Target-region visibility helpers for patch camera selection."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median

from reefs.patches.artefacts import SparseImage, SparsePoint, SparseScene
from reefs.patches.bounds import PatchBounds


TARGET_CELLS_PER_IMAGE = 5
MIN_TARGET_CELLS_PER_PATCH = 4


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


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((percentile / 100.0) * (len(ordered) - 1)))))
    return ordered[index]


def _robust_values(values: list[float]) -> list[float]:
    if len(values) < 6:
        return values
    low = _percentile(values, 5)
    high = _percentile(values, 95)
    return [value for value in values if low <= value <= high]


def _robust_target_z(scene: SparseScene, bounds: PatchBounds, patch_points: list[SparsePoint]) -> float:
    z_values = _robust_values([point.xyz[2] for point in patch_points])
    if not z_values:
        nearby = [
            point.xyz[2]
            for point in scene.points
            if bounds.min_x - bounds.buffer <= point.xyz[0] <= bounds.max_x + bounds.buffer
            and bounds.min_y - bounds.buffer <= point.xyz[1] <= bounds.max_y + bounds.buffer
        ]
        z_values = _robust_values(nearby)
    if not z_values:
        z_values = [point.xyz[2] for point in scene.points]
    if not z_values:
        z_values = [image.center[2] for image in scene.images]
    if not z_values:
        return (bounds.min_z + bounds.max_z) / 2.0
    return float(median(z_values))


def _target_cell_count(scene: SparseScene, bounds: PatchBounds, all_bounds: list[PatchBounds] | None) -> int:
    """Allocate full-scene target cells to this patch by rectangle area."""
    scene_cells = max(MIN_TARGET_CELLS_PER_PATCH, round(len(scene.images) / TARGET_CELLS_PER_IMAGE))
    patch_bounds = all_bounds or [bounds]
    total_area = sum(max(0.0, item.width * item.height) for item in patch_bounds)
    if total_area <= 0.0:
        return scene_cells
    patch_area = max(0.0, bounds.width * bounds.height)
    return max(MIN_TARGET_CELLS_PER_PATCH, round(scene_cells * patch_area / total_area))


def _grid_dimensions(bounds: PatchBounds, target_cells: int) -> tuple[int, int]:
    """Return aspect-aware grid dimensions whose product is near target_cells."""
    target_cells = max(MIN_TARGET_CELLS_PER_PATCH, target_cells)
    aspect = max(bounds.width, 1e-9) / max(bounds.height, 1e-9)
    x_count = max(1, round(math.sqrt(target_cells * aspect)))
    y_count = max(1, math.ceil(target_cells / x_count))
    return x_count, y_count


def _cell_z_values(points: list[SparsePoint], bounds: PatchBounds, x_count: int, y_count: int) -> dict[tuple[int, int], list[float]]:
    values: dict[tuple[int, int], list[float]] = {}
    width = max(bounds.width, 1e-9)
    height = max(bounds.height, 1e-9)
    for point in points:
        if not bounds.contains_xy(point.xyz[0], point.xyz[1]):
            continue
        x_index = min(x_count - 1, max(0, int(((point.xyz[0] - bounds.min_x) / width) * x_count)))
        y_index = min(y_count - 1, max(0, int(((point.xyz[1] - bounds.min_y) / height) * y_count)))
        values.setdefault((x_index, y_index), []).append(point.xyz[2])
    return {cell: _robust_values(z_values) for cell, z_values in values.items()}


def _neighbour_z_values(
    values_by_cell: dict[tuple[int, int], list[float]],
    cell: tuple[int, int],
    *,
    x_count: int,
    y_count: int,
) -> list[float]:
    x_index, y_index = cell
    values: list[float] = []
    for y_neighbour in range(max(0, y_index - 1), min(y_count, y_index + 2)):
        for x_neighbour in range(max(0, x_index - 1), min(x_count, x_index + 2)):
            values.extend(values_by_cell.get((x_neighbour, y_neighbour), []))
    return _robust_values(values)


def _representative_z_values(z_values: list[float], fallback_z: float) -> list[float]:
    """Return one height for flat cells and more where observed structure is tall."""
    if not z_values:
        return [fallback_z]
    clean = _robust_values(z_values)
    if not clean:
        return [fallback_z]
    z_range = max(clean) - min(clean)
    if len(clean) < 8 or z_range <= 0.25:
        return [float(median(clean))]
    if z_range <= 1.0:
        return [float(_percentile(clean, 25)), float(_percentile(clean, 75))]
    return [float(_percentile(clean, 20)), float(_percentile(clean, 50)), float(_percentile(clean, 80))]


def build_target_samples(
    scene: SparseScene,
    bounds: PatchBounds,
    patch_points: list[SparsePoint],
    *,
    all_bounds: list[PatchBounds] | None = None,
) -> list[TargetSample]:
    """Build scene-scaled, aspect-aware target samples inside a patch."""
    target_cell_count = _target_cell_count(scene, bounds, all_bounds)
    x_count, y_count = _grid_dimensions(bounds, target_cell_count)
    fallback_z = _robust_target_z(scene, bounds, patch_points)
    values_by_cell = _cell_z_values(patch_points, bounds, x_count, y_count)
    samples: list[TargetSample] = []
    sample_id = 0
    for y_index in range(y_count):
        y = bounds.min_y + ((y_index + 0.5) / y_count) * bounds.height
        for x_index in range(x_count):
            x = bounds.min_x + ((x_index + 0.5) / x_count) * bounds.width
            local_z_values = values_by_cell.get((x_index, y_index), [])
            if not local_z_values:
                local_z_values = _neighbour_z_values(values_by_cell, (x_index, y_index), x_count=x_count, y_count=y_count)
            for z_index, target_z in enumerate(_representative_z_values(local_z_values, fallback_z)):
                role = "boundary" if bounds.is_boundary_xy(x, y) else "body"
                samples.append(
                    TargetSample(
                        sample_id=sample_id,
                        xyz=(x, y, target_z),
                        role=role,
                        cell_id=f"{x_index}:{y_index}:{z_index}",
                    )
                )
                sample_id += 1
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
