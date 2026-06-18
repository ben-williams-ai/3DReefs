"""Camera Selection V3 helpers for patch splat training."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from reefs.patches.artefacts import SparseCamera, SparseImage, SparsePoint, SparseScene
from reefs.patches.bounds import PatchBounds


SELECTOR_NAME = "camera_selection_v3"
SELECTOR_VERSION = "v3"
MIN_TARGET_IMAGE_SHARE = 0.05
NEAR_TARGET_IMAGE_SHARE_MARGIN = 0.01
LOW_PATCH_FOOTPRINT_COVERAGE = 0.25
EXTERNAL_EVIDENCE_WEIGHT = 0.75
EXTERNAL_AZIMUTH_WEIGHT = 0.25
AZIMUTH_SECTOR_COUNT = 8


def derive_patch_camera_targets(max_cameras: int, external_support_fraction: float) -> dict[str, int | float]:
    """Return V3 final cap, external allowance, and internal target."""
    if max_cameras <= 0:
        raise ValueError("max_cameras must be positive")
    if not 0.0 <= external_support_fraction <= 1.0:
        raise ValueError("external_support_fraction must be between 0 and 1")
    external_support_allowance = math.floor(max_cameras * external_support_fraction)
    internal_patch_target = max_cameras - external_support_allowance
    if internal_patch_target <= 0:
        raise ValueError("internal_patch_target must be positive")
    return {
        "max_cameras": max_cameras,
        "external_support_fraction": external_support_fraction,
        "external_support_allowance": external_support_allowance,
        "internal_patch_target": internal_patch_target,
    }


def selector_settings(
    *,
    max_cameras: int | None = None,
    external_support_fraction: float = 0.10,
) -> dict[str, object]:
    """Return selector-affecting settings for patch reuse checks."""
    settings: dict[str, object] = {
        "name": SELECTOR_NAME,
        "version": SELECTOR_VERSION,
        "candidate_pool": "internal_plus_one_ring_neighbours",
        "signals": ["patch_tracks_seen", "footprint_overlap", "target_image_share"],
        "footprint_geometry": "image_corner_frustum_intersected_with_patch_rectangle_on_scene_xy_plane",
        "target_image_geometry": "project_patch_frustum_intersection_polygon_to_image",
        "min_target_image_share": MIN_TARGET_IMAGE_SHARE,
        "near_min_target_image_share_margin": NEAR_TARGET_IMAGE_SHARE_MARGIN,
        "low_patch_footprint_coverage": LOW_PATCH_FOOTPRINT_COVERAGE,
        "external_evidence_weight": EXTERNAL_EVIDENCE_WEIGHT,
        "external_azimuth_weight": EXTERNAL_AZIMUTH_WEIGHT,
        "azimuth_sector_count": AZIMUTH_SECTOR_COUNT,
    }
    if max_cameras is not None:
        settings.update(derive_patch_camera_targets(max_cameras, external_support_fraction))
    else:
        settings["external_support_fraction"] = external_support_fraction
    return settings


@dataclass(frozen=True)
class CameraSelectionScore:
    """V3 per-camera evidence used for patch selection and diagnostics."""

    image_id: int
    image_name: str
    source_patch: str
    pool: str
    selection_role: str
    azimuth_sector: int
    azimuth_degrees: float
    visible_patch_track_count: int
    normalised_track_score: float
    footprint_overlap_score: float
    target_image_share: float
    external_evidence_score: float
    azimuth_spread_score: float
    external_score: float
    camera_x: float
    camera_y: float
    camera_z: float
    selected: bool = False

    @property
    def local(self) -> bool:
        """Compatibility alias for internal cameras."""
        return self.pool == "internal"

    @property
    def visible_patch_points(self) -> int:
        """Compatibility alias for visible patch tracks."""
        return self.visible_patch_track_count

    @property
    def total_visible_points(self) -> int:
        """Compatibility alias for visible patch tracks."""
        return self.visible_patch_track_count

    @property
    def score(self) -> float:
        """Return the scalar score relevant to this camera."""
        return self.external_score if self.pool == "external" else self.normalised_track_score

    def ranking_tuple(self) -> tuple[float, float, float, str]:
        """Return deterministic V3 diagnostic ordering."""
        role_order = {
            "kept_internal": 0,
            "rejected_internal": 1,
            "selected_external": 2,
            "unused_external": 3,
        }
        return (
            float(role_order.get(self.selection_role, 9)),
            -float(self.selected),
            -float(self.score),
            self.image_name,
        )

    def with_role(self, *, selected: bool, selection_role: str) -> "CameraSelectionScore":
        """Return this score with final selection state changed."""
        return CameraSelectionScore(**{**self.as_constructor_dict(), "selected": selected, "selection_role": selection_role})

    def as_constructor_dict(self) -> dict[str, object]:
        """Return constructor-compatible score data."""
        return {
            "image_id": self.image_id,
            "image_name": self.image_name,
            "source_patch": self.source_patch,
            "pool": self.pool,
            "selection_role": self.selection_role,
            "azimuth_sector": self.azimuth_sector,
            "azimuth_degrees": self.azimuth_degrees,
            "visible_patch_track_count": self.visible_patch_track_count,
            "normalised_track_score": self.normalised_track_score,
            "footprint_overlap_score": self.footprint_overlap_score,
            "target_image_share": self.target_image_share,
            "external_evidence_score": self.external_evidence_score,
            "azimuth_spread_score": self.azimuth_spread_score,
            "external_score": self.external_score,
            "camera_x": self.camera_x,
            "camera_y": self.camera_y,
            "camera_z": self.camera_z,
            "selected": self.selected,
        }

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable diagnostic score."""
        return self.as_constructor_dict()


@dataclass(frozen=True)
class PatchSelection:
    """Selected images and supporting diagnostics for one patch."""

    bounds: PatchBounds
    selected_images: list[SparseImage]
    local_images: list[SparseImage]
    support_images: list[SparseImage]
    patch_points: list[SparsePoint]
    camera_scores: list[CameraSelectionScore]
    warnings: list[str]
    neighbour_bounds: list[PatchBounds]
    max_cameras: int
    external_support_fraction: float
    external_support_allowance: int
    internal_patch_target: int

    @property
    def selected_internal_count(self) -> int:
        return len([score for score in self.camera_scores if score.selection_role == "kept_internal"])

    @property
    def rejected_internal_count(self) -> int:
        return len([score for score in self.camera_scores if score.selection_role == "rejected_internal"])

    @property
    def selected_external_count(self) -> int:
        return len([score for score in self.camera_scores if score.selection_role == "selected_external"])

    @property
    def unused_external_count(self) -> int:
        return len([score for score in self.camera_scores if score.selection_role == "unused_external"])

    @property
    def patch_footprint_coverage(self) -> float:
        selected = [score.footprint_overlap_score for score in self.camera_scores if score.selected]
        return min(1.0, sum(selected))

    @property
    def selected_target_image_shares(self) -> list[float]:
        return [score.target_image_share for score in self.camera_scores if score.selected]

    def coverage_summary(self) -> dict[str, object]:
        """Return V3 selector coverage metadata."""
        shares = self.selected_target_image_shares
        selected_scores = [score for score in self.camera_scores if score.selected]
        track_scores = [score.normalised_track_score for score in selected_scores]
        footprint_scores = [score.footprint_overlap_score for score in selected_scores]
        return {
            "selected_internal_count": self.selected_internal_count,
            "rejected_internal_count": self.rejected_internal_count,
            "selected_external_count": self.selected_external_count,
            "unused_external_count": self.unused_external_count,
            "max_cameras": self.max_cameras,
            "external_support_fraction": self.external_support_fraction,
            "external_support_allowance": self.external_support_allowance,
            "internal_patch_target": self.internal_patch_target,
            "patch_footprint_coverage": self.patch_footprint_coverage,
            "target_image_share_min": min(shares) if shares else 0.0,
            "target_image_share_median": _median(shares) if shares else 0.0,
            "selected_track_score_median": _median(track_scores) if track_scores else 0.0,
            "selected_footprint_overlap_median": _median(footprint_scores) if footprint_scores else 0.0,
        }

    def warning_thresholds(self) -> dict[str, object]:
        """Return warning thresholds used for this selection."""
        return {
            "min_target_image_share": MIN_TARGET_IMAGE_SHARE,
            "near_min_target_image_share_margin": NEAR_TARGET_IMAGE_SHARE_MARGIN,
            "low_patch_footprint_coverage": LOW_PATCH_FOOTPRINT_COVERAGE,
        }

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable selection summary."""
        return {
            "patch_id": self.bounds.patch_id,
            "selected_images": [image.name for image in self.selected_images],
            "selected_camera_count": len(self.selected_images),
            "selected_internal_count": self.selected_internal_count,
            "rejected_internal_count": self.rejected_internal_count,
            "selected_external_count": self.selected_external_count,
            "unused_external_count": self.unused_external_count,
            "selected_local_count": self.selected_internal_count,
            "selected_support_count": self.selected_external_count,
            "sparse_point_count": len(self.patch_points),
            "max_cameras": self.max_cameras,
            "external_support_fraction": self.external_support_fraction,
            "external_support_allowance": self.external_support_allowance,
            "internal_patch_target": self.internal_patch_target,
            "warnings": self.warnings,
        }


def discover_one_ring_neighbours(bounds: list[PatchBounds], anchor: PatchBounds) -> list[PatchBounds]:
    """Return patches spatially adjacent to an anchor patch."""
    anchor_cx, anchor_cy = anchor.centre
    neighbours: list[PatchBounds] = []
    for candidate in bounds:
        if candidate.patch_id == anchor.patch_id:
            continue
        cand_cx, cand_cy = candidate.centre
        max_dx = (anchor.width + candidate.width) / 2.0 + 1e-6
        max_dy = (anchor.height + candidate.height) / 2.0 + 1e-6
        if abs(cand_cx - anchor_cx) <= max_dx and abs(cand_cy - anchor_cy) <= max_dy:
            neighbours.append(candidate)
    return neighbours


def _polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    twice_area = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        twice_area += point[0] * next_point[1] - next_point[0] * point[1]
    return abs(twice_area) * 0.5


def _convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    unique_points = sorted(set(points))
    if len(unique_points) <= 1:
        return unique_points

    def cross(origin: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return ((a[0] - origin[0]) * (b[1] - origin[1])) - ((a[1] - origin[1]) * (b[0] - origin[0]))

    lower: list[tuple[float, float]] = []
    for point in unique_points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)

    upper: list[tuple[float, float]] = []
    for point in reversed(unique_points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def _azimuth_sector(camera_x: float, camera_y: float, centre_x: float, centre_y: float) -> tuple[int, float]:
    angle = (math.degrees(math.atan2(camera_y - centre_y, camera_x - centre_x)) + 360.0) % 360.0
    sector_width = 360.0 / AZIMUTH_SECTOR_COUNT
    return int(angle // sector_width) % AZIMUTH_SECTOR_COUNT, angle


def _local_images_for_bounds(scene: SparseScene, bounds: PatchBounds) -> list[SparseImage]:
    return [image for image in scene.images if bounds.contains_xy(image.center[0], image.center[1])]


def _camera_intrinsics(camera: SparseCamera | None, image: SparseImage) -> tuple[float, float, float, float] | None:
    """Return pinhole-style `fx, fy, cx, cy` for frustum footprint scoring."""
    if camera is None:
        return None
    params = camera.params
    model = camera.model.upper()
    if model in {"SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL"} and len(params) >= 3:
        return params[0], params[0], params[1], params[2]
    if model in {"PINHOLE", "OPENCV", "OPENCV_FISHEYE", "FULL_OPENCV"} and len(params) >= 4:
        return params[0], params[1], params[2], params[3]
    if image.width > 0 and image.height > 0:
        f = float(max(image.width, image.height))
        return f, f, image.width / 2.0, image.height / 2.0
    return None


def _rotation_transpose_multiply(
    qvec: tuple[float, float, float, float],
    vector: tuple[float, float, float],
) -> tuple[float, float, float]:
    rotation = _quaternion_to_rotation_matrix(qvec)
    return (
        sum(rotation[row][0] * vector[row] for row in range(3)),
        sum(rotation[row][1] * vector[row] for row in range(3)),
        sum(rotation[row][2] * vector[row] for row in range(3)),
    )


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


def _world_to_camera(
    image: SparseImage,
    point: tuple[float, float, float],
) -> tuple[float, float, float]:
    rotation = _quaternion_to_rotation_matrix(image.qvec)
    return (
        sum(rotation[0][axis] * point[axis] for axis in range(3)) + image.tvec[0],
        sum(rotation[1][axis] * point[axis] for axis in range(3)) + image.tvec[1],
        sum(rotation[2][axis] * point[axis] for axis in range(3)) + image.tvec[2],
    )


def _project_world_point(
    image: SparseImage,
    intrinsics: tuple[float, float, float, float],
    point: tuple[float, float, float],
) -> tuple[float, float] | None:
    fx, fy, cx, cy = intrinsics
    x, y, z = _world_to_camera(image, point)
    if z <= 1e-9:
        return None
    return fx * (x / z) + cx, fy * (y / z) + cy


def _ray_plane_intersection(
    image: SparseImage,
    intrinsics: tuple[float, float, float, float],
    pixel: tuple[float, float],
    plane_z: float,
) -> tuple[float, float] | None:
    fx, fy, cx, cy = intrinsics
    direction_camera = ((pixel[0] - cx) / fx, (pixel[1] - cy) / fy, 1.0)
    direction_world = _rotation_transpose_multiply(image.qvec, direction_camera)
    dz = direction_world[2]
    if abs(dz) <= 1e-9:
        return None
    scale = (plane_z - image.center[2]) / dz
    if scale <= 0.0:
        return None
    return image.center[0] + scale * direction_world[0], image.center[1] + scale * direction_world[1]


def _frustum_footprint_xy(
    image: SparseImage,
    intrinsics: tuple[float, float, float, float],
    *,
    plane_z: float = 0.0,
) -> list[tuple[float, float]]:
    width = float(image.width)
    height = float(image.height)
    corners = [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]
    points = [_ray_plane_intersection(image, intrinsics, corner, plane_z) for corner in corners]
    return [point for point in points if point is not None]


def _clip_polygon_to_rect(
    polygon: list[tuple[float, float]],
    bounds: PatchBounds,
) -> list[tuple[float, float]]:
    def clip(
        points: list[tuple[float, float]],
        inside,
        intersect,
    ) -> list[tuple[float, float]]:
        if not points:
            return []
        output: list[tuple[float, float]] = []
        previous = points[-1]
        previous_inside = inside(previous)
        for current in points:
            current_inside = inside(current)
            if current_inside:
                if not previous_inside:
                    output.append(intersect(previous, current))
                output.append(current)
            elif previous_inside:
                output.append(intersect(previous, current))
            previous = current
            previous_inside = current_inside
        return output

    def x_intersection(x_value: float):
        return lambda a, b: (x_value, a[1] + (b[1] - a[1]) * ((x_value - a[0]) / (b[0] - a[0])))

    def y_intersection(y_value: float):
        return lambda a, b: (a[0] + (b[0] - a[0]) * ((y_value - a[1]) / (b[1] - a[1])), y_value)

    clipped = clip(polygon, lambda p: p[0] >= bounds.min_x, x_intersection(bounds.min_x))
    clipped = clip(clipped, lambda p: p[0] <= bounds.max_x, x_intersection(bounds.max_x))
    clipped = clip(clipped, lambda p: p[1] >= bounds.min_y, y_intersection(bounds.min_y))
    return clip(clipped, lambda p: p[1] <= bounds.max_y, y_intersection(bounds.max_y))


def _footprint_scores(
    bounds: PatchBounds,
    image: SparseImage,
    camera: SparseCamera | None,
) -> tuple[float, float]:
    intrinsics = _camera_intrinsics(camera, image)
    if intrinsics is None or image.width <= 0 or image.height <= 0:
        return 0.0, 0.0
    frustum = _frustum_footprint_xy(image, intrinsics)
    if len(frustum) < 3:
        return 0.0, 0.0
    intersection = _clip_polygon_to_rect(frustum, bounds)
    if len(intersection) < 3:
        return 0.0, 0.0
    footprint_overlap_score = min(1.0, _polygon_area(intersection) / max(bounds.width * bounds.height, 1e-12))
    projected = [
        _project_world_point(image, intrinsics, (x, y, 0.0))
        for x, y in intersection
    ]
    projected_points = [point for point in projected if point is not None]
    if len(projected_points) < 3:
        return footprint_overlap_score, 0.0
    image_area = float(image.width * image.height)
    target_image_share = min(1.0, _polygon_area(_convex_hull(projected_points)) / image_area)
    return footprint_overlap_score, target_image_share


def _camera_evidence_score(
    *,
    normalised_track_score: float,
    footprint_overlap_score: float,
    target_image_share: float,
) -> float:
    return (normalised_track_score + footprint_overlap_score + target_image_share) / 3.0


def _score_candidate_cameras(
    scene: SparseScene,
    bounds: PatchBounds,
    *,
    internal_images: list[SparseImage],
    external_images: list[SparseImage],
    external_source_by_id: dict[int, str],
) -> list[CameraSelectionScore]:
    patch_points = [point for point in scene.points if bounds.contains_xy(point.xyz[0], point.xyz[1])]
    patch_point_ids = {point.point_id for point in patch_points}
    track_counts: dict[int, int] = {}
    candidate_images = [*internal_images, *external_images]

    for image in candidate_images:
        track_counts[image.image_id] = len(
            {observation.point3d_id for observation in image.observations if observation.point3d_id in patch_point_ids}
        )

    positive_counts = [count for count in track_counts.values() if count > 0]
    median_visible_patch_track_count = _median([float(count) for count in positive_counts]) or 1.0
    centre_x, centre_y = bounds.centre
    internal_ids = {image.image_id for image in internal_images}

    scores: list[CameraSelectionScore] = []
    for image in candidate_images:
        visible_patch_track_count = track_counts.get(image.image_id, 0)
        normalised_track_score = min(1.0, visible_patch_track_count / median_visible_patch_track_count)
        footprint_overlap_score, target_image_share = _footprint_scores(
            bounds,
            image,
            scene.cameras.get(image.camera_id),
        )
        external_evidence_score = _camera_evidence_score(
            normalised_track_score=normalised_track_score,
            footprint_overlap_score=footprint_overlap_score,
            target_image_share=target_image_share,
        )
        sector, angle = _azimuth_sector(image.center[0], image.center[1], centre_x, centre_y)
        pool = "internal" if image.image_id in internal_ids else "external"
        scores.append(
            CameraSelectionScore(
                image_id=image.image_id,
                image_name=image.name,
                source_patch=bounds.patch_id if pool == "internal" else external_source_by_id.get(image.image_id, "external"),
                pool=pool,
                selection_role="rejected_internal" if pool == "internal" else "unused_external",
                azimuth_sector=sector,
                azimuth_degrees=angle,
                visible_patch_track_count=visible_patch_track_count,
                normalised_track_score=normalised_track_score,
                footprint_overlap_score=footprint_overlap_score,
                target_image_share=target_image_share,
                external_evidence_score=external_evidence_score,
                azimuth_spread_score=0.0,
                external_score=external_evidence_score,
                camera_x=image.center[0],
                camera_y=image.center[1],
                camera_z=image.center[2],
            )
        )
    return scores


def _is_useful(score: CameraSelectionScore) -> bool:
    return score.target_image_share >= MIN_TARGET_IMAGE_SHARE and (
        score.visible_patch_track_count > 0 or score.footprint_overlap_score > 0
    )


def _angle_distance_degrees(left: float, right: float) -> float:
    return abs((left - right + 180.0) % 360.0 - 180.0)


def _rank_external_support(scores: list[CameraSelectionScore], capacity: int) -> list[CameraSelectionScore]:
    remaining = [score for score in scores if _is_useful(score)]
    selected: list[CameraSelectionScore] = []
    while remaining and len(selected) < capacity:
        ranked: list[CameraSelectionScore] = []
        for score in remaining:
            if not selected:
                azimuth_spread_score = 1.0
            else:
                nearest = min(_angle_distance_degrees(score.azimuth_degrees, item.azimuth_degrees) for item in selected)
                azimuth_spread_score = math.log1p(nearest) / math.log1p(180.0)
            external_score = (EXTERNAL_EVIDENCE_WEIGHT * score.external_evidence_score) + (
                EXTERNAL_AZIMUTH_WEIGHT * azimuth_spread_score
            )
            ranked.append(
                CameraSelectionScore(
                    **{
                        **score.as_constructor_dict(),
                        "azimuth_spread_score": azimuth_spread_score,
                        "external_score": external_score,
                    }
                )
            )
        ranked.sort(key=lambda item: (-item.external_score, item.image_name))
        winner = ranked[0]
        selected.append(winner)
        remaining = [score for score in remaining if score.image_id != winner.image_id]
    return selected


def sort_scores(scores: Iterable[CameraSelectionScore]) -> list[CameraSelectionScore]:
    """Sort camera scores for deterministic diagnostics."""
    return sorted(scores, key=lambda score: score.ranking_tuple())


def select_patch_views(
    scene: SparseScene,
    bounds: PatchBounds,
    *,
    max_cameras: int,
    all_bounds: list[PatchBounds] | None = None,
    external_support_fraction: float = 0.10,
) -> PatchSelection:
    """Select V3 patch cameras: useful internal first, capped neighbouring support second."""
    targets = derive_patch_camera_targets(max_cameras, external_support_fraction)
    external_support_allowance = int(targets["external_support_allowance"])
    internal_patch_target = int(targets["internal_patch_target"])
    patch_points = [point for point in scene.points if bounds.contains_xy(point.xyz[0], point.xyz[1])]
    all_patch_bounds = all_bounds or [bounds]
    neighbours = discover_one_ring_neighbours(all_patch_bounds, bounds)
    internal_images = _local_images_for_bounds(scene, bounds)
    internal_ids = {image.image_id for image in internal_images}

    external_by_id: dict[int, SparseImage] = {}
    external_source_by_id: dict[int, str] = {}
    for neighbour in neighbours:
        for image in _local_images_for_bounds(scene, neighbour):
            if image.image_id in internal_ids:
                continue
            external_by_id.setdefault(image.image_id, image)
            external_source_by_id.setdefault(image.image_id, neighbour.patch_id)
    external_images = list(external_by_id.values())

    scores = _score_candidate_cameras(
        scene,
        bounds,
        internal_images=internal_images,
        external_images=external_images,
        external_source_by_id=external_source_by_id,
    )
    useful_internal = [score for score in scores if score.pool == "internal" and _is_useful(score)]
    if len(useful_internal) > max_cameras:
        raise ValueError(
            f"{bounds.patch_id} has {len(useful_internal)} useful internal cameras, exceeding max_cameras={max_cameras}; "
            "patch bounds failed the V3 sizing invariant"
        )

    remaining_capacity = max_cameras - len(useful_internal)
    external_capacity = min(external_support_allowance, remaining_capacity)
    ranked_external = _rank_external_support(
        [score for score in scores if score.pool == "external"],
        external_capacity if external_support_fraction > 0 else 0,
    )
    selected_ids = {score.image_id for score in [*useful_internal, *ranked_external]}
    selected_external_ids = {score.image_id for score in ranked_external}

    final_scores: list[CameraSelectionScore] = []
    external_score_by_id = {score.image_id: score for score in ranked_external}
    for score in scores:
        enriched = external_score_by_id.get(score.image_id, score)
        if enriched.pool == "internal":
            role = "kept_internal" if enriched.image_id in selected_ids else "rejected_internal"
        else:
            role = "selected_external" if enriched.image_id in selected_external_ids else "unused_external"
        final_scores.append(enriched.with_role(selected=enriched.image_id in selected_ids, selection_role=role))

    selected_images = [scene.image_by_id[score.image_id] for score in sort_scores(final_scores) if score.selected]
    warnings: list[str] = []
    if not patch_points:
        warnings.append("No sparse points fall inside patch bounds.")
    if not scores:
        warnings.append("No internal or one-ring external cameras were found for patch.")
    if len(useful_internal) > internal_patch_target:
        warnings.append(
            f"Useful internal camera count {len(useful_internal)} exceeds internal_patch_target={internal_patch_target}."
        )
    if len(selected_images) >= max_cameras:
        warnings.append(f"Selection reached max_cameras={max_cameras}.")
    selected_shares = [score.target_image_share for score in final_scores if score.selected]
    if selected_shares and min(selected_shares) <= MIN_TARGET_IMAGE_SHARE + NEAR_TARGET_IMAGE_SHARE_MARGIN:
        warnings.append("Selected camera target image share is near the minimum threshold.")
    patch_footprint_coverage = min(1.0, sum(score.footprint_overlap_score for score in final_scores if score.selected))
    if patch_footprint_coverage < LOW_PATCH_FOOTPRINT_COVERAGE:
        warnings.append(f"Patch footprint coverage is low ({patch_footprint_coverage:.3f}).")

    return PatchSelection(
        bounds=bounds,
        selected_images=selected_images,
        local_images=internal_images,
        support_images=external_images,
        patch_points=patch_points,
        camera_scores=sort_scores(final_scores),
        warnings=warnings,
        neighbour_bounds=neighbours,
        max_cameras=max_cameras,
        external_support_fraction=external_support_fraction,
        external_support_allowance=external_support_allowance,
        internal_patch_target=internal_patch_target,
    )
