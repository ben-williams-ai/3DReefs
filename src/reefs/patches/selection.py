"""Old-style view-based camera scoring and selection helpers."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from reefs.patches.artefacts import SparseImage, SparsePoint, SparseScene
from reefs.patches.bounds import PatchBounds


SELECTOR_NAME = "old_view_based_selector"
SELECTOR_VERSION = "pre_v3_baseline"


def selector_settings() -> dict[str, object]:
    """Return selector-affecting settings for patch reuse checks."""
    return {
        "name": SELECTOR_NAME,
        "version": SELECTOR_VERSION,
        "azimuth_sectors": 8,
        "candidate_pool": "internal_plus_one_ring_neighbours",
    }


@dataclass(frozen=True)
class CameraSelectionScore:
    """Camera score used for old-style view-based patch selection."""

    image_id: int
    image_name: str
    source_patch: str
    pool: str
    azimuth_sector: int
    azimuth_degrees: float
    core_visible_points: int
    boundary_visible_points: int
    interior_visible_points: int
    projected_core_area_ratio: float
    projected_boundary_area_ratio: float
    projected_interior_area_ratio: float
    median_visible_depth: float
    camera_x: float
    camera_y: float
    camera_z: float
    selected: bool = False

    @property
    def local(self) -> bool:
        """Return whether this camera belongs to the anchor patch pool."""
        return self.pool == "local"

    @property
    def visible_patch_points(self) -> int:
        """Compatibility alias for all visible patch points."""
        return self.core_visible_points

    @property
    def total_visible_points(self) -> int:
        """Compatibility alias for all visible patch points."""
        return self.core_visible_points

    @property
    def score(self) -> float:
        """Return a coarse scalar score for legacy summaries."""
        return float(self.boundary_visible_points) + self.projected_boundary_area_ratio

    def ranking_tuple(self) -> tuple[float, float, float, float, float, str]:
        """Return deterministic old-style ranking tuple."""
        return (
            -float(self.boundary_visible_points),
            -float(self.projected_boundary_area_ratio),
            -float(self.core_visible_points),
            -float(self.projected_core_area_ratio),
            float(self.median_visible_depth),
            self.image_name,
        )

    def with_selected(self, selected: bool) -> "CameraSelectionScore":
        """Return this score with selection state changed."""
        return CameraSelectionScore(**{**self.as_constructor_dict(), "selected": selected})

    def as_constructor_dict(self) -> dict[str, object]:
        """Return constructor-compatible score data."""
        return {
            "image_id": self.image_id,
            "image_name": self.image_name,
            "source_patch": self.source_patch,
            "pool": self.pool,
            "azimuth_sector": self.azimuth_sector,
            "azimuth_degrees": self.azimuth_degrees,
            "core_visible_points": self.core_visible_points,
            "boundary_visible_points": self.boundary_visible_points,
            "interior_visible_points": self.interior_visible_points,
            "projected_core_area_ratio": self.projected_core_area_ratio,
            "projected_boundary_area_ratio": self.projected_boundary_area_ratio,
            "projected_interior_area_ratio": self.projected_interior_area_ratio,
            "median_visible_depth": self.median_visible_depth,
            "camera_x": self.camera_x,
            "camera_y": self.camera_y,
            "camera_z": self.camera_z,
            "selected": self.selected,
        }

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable diagnostic score."""
        return {
            "image_id": self.image_id,
            "image_name": self.image_name,
            "selection_role": "selected" if self.selected else "unselected",
            "pool": self.pool,
            "source_patch": self.source_patch,
            "core_projection_portion": self.projected_interior_area_ratio,
            "boundary_projection_area": self.projected_boundary_area_ratio,
            "combined_projection_portion": self.projected_core_area_ratio,
            "core_visible_points": self.interior_visible_points,
            "boundary_visible_points": self.boundary_visible_points,
            "combined_visible_points": self.core_visible_points,
            "median_visible_depth": self.median_visible_depth,
            "azimuth_sector": self.azimuth_sector,
            "camera_x": self.camera_x,
            "camera_y": self.camera_y,
            "camera_z": self.camera_z,
        }


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

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable selection summary."""
        selected_ids = {image.image_id for image in self.selected_images}
        local_ids = {image.image_id for image in self.local_images}
        support_ids = {image.image_id for image in self.support_images}
        return {
            "patch_id": self.bounds.patch_id,
            "selected_images": [image.name for image in self.selected_images],
            "selected_camera_count": len(self.selected_images),
            "selected_local_count": len(selected_ids & local_ids),
            "selected_support_count": len(selected_ids & support_ids),
            "sparse_point_count": len(self.patch_points),
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


def _projected_area_ratio(points: list[tuple[float, float]], width: int, height: int) -> float:
    if len(points) < 3 or width <= 0 or height <= 0:
        return 0.0
    return _polygon_area(_convex_hull(points)) / float(width * height)


def _median(values: list[float]) -> float:
    if not values:
        return float("inf")
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def _azimuth_sector(camera_x: float, camera_y: float, centre_x: float, centre_y: float) -> tuple[int, float]:
    angle = (math.degrees(math.atan2(camera_y - centre_y, camera_x - centre_x)) + 360.0) % 360.0
    return int(angle // 45.0) % 8, angle


def sort_scores(scores: Iterable[CameraSelectionScore]) -> list[CameraSelectionScore]:
    """Sort camera scores with old boundary-first ranking."""
    return sorted(scores, key=lambda score: score.ranking_tuple())


def balanced_sector_selection(scores: list[CameraSelectionScore], target_count: int) -> list[CameraSelectionScore]:
    """Select cameras with deterministic 8-sector balancing."""
    if target_count <= 0:
        return []
    per_sector: dict[int, list[CameraSelectionScore]] = defaultdict(list)
    for score in sort_scores(scores):
        per_sector[score.azimuth_sector].append(score)

    selected: list[CameraSelectionScore] = []
    picks_by_sector: dict[int, int] = defaultdict(int)
    ordered_sectors = sorted(per_sector)
    for sector in ordered_sectors:
        if len(selected) >= target_count:
            break
        if per_sector[sector]:
            selected.append(per_sector[sector].pop(0))
            picks_by_sector[sector] += 1

    while len(selected) < target_count and any(per_sector.values()):
        candidate_sector: int | None = None
        candidate_ratio: float | None = None
        for sector in ordered_sectors:
            if not per_sector[sector]:
                continue
            ratio = picks_by_sector[sector] / max(1, len(per_sector[sector]) + picks_by_sector[sector])
            if candidate_ratio is None or ratio < candidate_ratio or (
                math.isclose(ratio, candidate_ratio) and candidate_sector is not None and sector < candidate_sector
            ):
                candidate_sector = sector
                candidate_ratio = ratio
        if candidate_sector is None:
            break
        selected.append(per_sector[candidate_sector].pop(0))
        picks_by_sector[candidate_sector] += 1
    return selected[:target_count]


def _local_images_for_bounds(scene: SparseScene, bounds: PatchBounds) -> list[SparseImage]:
    return [image for image in scene.images if bounds.contains_xy(image.center[0], image.center[1])]


def _score_candidate_cameras(
    scene: SparseScene,
    bounds: PatchBounds,
    *,
    local_images: list[SparseImage],
    support_images: list[SparseImage],
) -> list[CameraSelectionScore]:
    candidate_images = {image.image_id: image for image in [*local_images, *support_images]}
    local_ids = {image.image_id for image in local_images}
    support_source_by_image = {image.image_id: "support" for image in support_images}
    centre_x, centre_y = bounds.centre
    observations_by_image = {image.image_id: image.observations for image in scene.images}

    buckets: dict[int, dict[str, object]] = defaultdict(
        lambda: {
            "core_xy": [],
            "boundary_xy": [],
            "interior_xy": [],
            "core_depths": [],
            "boundary_depths": [],
            "interior_depths": [],
            "core_seen": set(),
            "boundary_seen": set(),
            "interior_seen": set(),
        }
    )

    for point in scene.points:
        x, y, z = point.xyz
        if not bounds.contains_xy(x, y):
            continue
        in_boundary = bounds.is_boundary_xy(x, y)
        for image_id, point2d_idx in point.track_pairs:
            image = candidate_images.get(image_id)
            if image is None:
                continue
            observations = observations_by_image.get(image_id, ())
            if point2d_idx < 0 or point2d_idx >= len(observations):
                continue
            observation = observations[point2d_idx]
            bucket = buckets[image_id]
            xy = (float(observation.x), float(observation.y))
            depth = float(math.dist((x, y, z), image.center))
            bucket["core_xy"].append(xy)  # type: ignore[union-attr]
            bucket["core_depths"].append(depth)  # type: ignore[union-attr]
            bucket["core_seen"].add(point.point_id)  # type: ignore[union-attr]
            if in_boundary:
                bucket["boundary_xy"].append(xy)  # type: ignore[union-attr]
                bucket["boundary_depths"].append(depth)  # type: ignore[union-attr]
                bucket["boundary_seen"].add(point.point_id)  # type: ignore[union-attr]
            else:
                bucket["interior_xy"].append(xy)  # type: ignore[union-attr]
                bucket["interior_depths"].append(depth)  # type: ignore[union-attr]
                bucket["interior_seen"].add(point.point_id)  # type: ignore[union-attr]

    scores: list[CameraSelectionScore] = []
    for image in candidate_images.values():
        bucket = buckets[image.image_id]
        sector, angle = _azimuth_sector(image.center[0], image.center[1], centre_x, centre_y)
        pool = "local" if image.image_id in local_ids else "support"
        source_patch = bounds.patch_id if pool == "local" else support_source_by_image.get(image.image_id, "support")
        scores.append(
            CameraSelectionScore(
                image_id=image.image_id,
                image_name=image.name,
                source_patch=source_patch,
                pool=pool,
                azimuth_sector=sector,
                azimuth_degrees=angle,
                core_visible_points=len(bucket["core_seen"]),  # type: ignore[arg-type]
                boundary_visible_points=len(bucket["boundary_seen"]),  # type: ignore[arg-type]
                interior_visible_points=len(bucket["interior_seen"]),  # type: ignore[arg-type]
                projected_core_area_ratio=_projected_area_ratio(bucket["core_xy"], image.width, image.height),  # type: ignore[arg-type]
                projected_boundary_area_ratio=_projected_area_ratio(bucket["boundary_xy"], image.width, image.height),  # type: ignore[arg-type]
                projected_interior_area_ratio=_projected_area_ratio(bucket["interior_xy"], image.width, image.height),  # type: ignore[arg-type]
                median_visible_depth=_median(bucket["boundary_depths"] or bucket["core_depths"]),  # type: ignore[arg-type]
                camera_x=image.center[0],
                camera_y=image.center[1],
                camera_z=image.center[2],
            )
        )
    return scores


def select_patch_views(
    scene: SparseScene,
    bounds: PatchBounds,
    *,
    max_cameras: int,
    all_bounds: list[PatchBounds] | None = None,
) -> PatchSelection:
    """Select cameras using old full-scene view-based balanced selection."""
    if max_cameras <= 0:
        raise ValueError("max_cameras must be positive")
    patch_points = [point for point in scene.points if bounds.contains_xy(point.xyz[0], point.xyz[1])]
    all_patch_bounds = all_bounds or [bounds]
    neighbours = discover_one_ring_neighbours(all_patch_bounds, bounds)
    local_images = _local_images_for_bounds(scene, bounds)
    support_by_id: dict[int, SparseImage] = {}
    support_source_by_id: dict[int, str] = {}
    local_ids = {image.image_id for image in local_images}
    for neighbour in neighbours:
        for image in _local_images_for_bounds(scene, neighbour):
            if image.image_id in local_ids:
                continue
            support_by_id.setdefault(image.image_id, image)
            support_source_by_id.setdefault(image.image_id, neighbour.patch_id)
    support_images = list(support_by_id.values())
    scores = _score_candidate_cameras(scene, bounds, local_images=local_images, support_images=support_images)
    if support_source_by_id:
        scores = [
            CameraSelectionScore(
                **{
                    **score.as_constructor_dict(),
                    "source_patch": support_source_by_id.get(score.image_id, score.source_patch)
                    if score.pool == "support"
                    else score.source_patch,
                }
            )
            for score in scores
        ]

    selected_scores = balanced_sector_selection([score for score in scores if score.core_visible_points > 0], max_cameras)
    selected_ids = {score.image_id for score in selected_scores}
    selected_images = [scene.image_by_id[score.image_id] for score in selected_scores if score.image_id in scene.image_by_id]
    camera_scores = [score.with_selected(score.image_id in selected_ids) for score in sort_scores(scores)]
    warnings: list[str] = []
    if not patch_points:
        warnings.append("No sparse points fall inside patch bounds.")
    if not scores:
        warnings.append("No local or one-ring support cameras were found for patch.")
    if scores and not selected_images:
        warnings.append("No candidate cameras observed sparse points inside patch bounds.")
    if len(selected_images) == max_cameras and len([score for score in scores if score.core_visible_points > 0]) > max_cameras:
        warnings.append(f"Selection capped at max_cameras={max_cameras}.")
    return PatchSelection(
        bounds=bounds,
        selected_images=selected_images,
        local_images=local_images,
        support_images=support_images,
        patch_points=patch_points,
        camera_scores=camera_scores,
        warnings=warnings,
        neighbour_bounds=neighbours,
    )
