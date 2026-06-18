"""Camera Selection V3 helpers for patch splat training."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from reefs.patches.artefacts import SparseImage, SparsePoint, SparseScene
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


def _point_lookup(scene: SparseScene) -> dict[int, SparsePoint]:
    return {point.point_id: point for point in scene.points}


def _observed_patch_points(
    image: SparseImage,
    patch_point_ids: set[int],
    point_by_id: dict[int, SparsePoint],
) -> list[tuple[float, float, float, float, float]]:
    observed: list[tuple[float, float, float, float, float]] = []
    for observation in image.observations:
        if observation.point3d_id not in patch_point_ids:
            continue
        point = point_by_id.get(observation.point3d_id)
        if point is None:
            continue
        x, y, _z = point.xyz
        observed.append((observation.x, observation.y, x, y, float(point.point_id)))
    return observed


def _target_image_share(image: SparseImage, observed: list[tuple[float, float, float, float, float]]) -> float:
    if image.width <= 0 or image.height <= 0 or len(observed) < 3:
        return 1.0 if observed else 0.0
    image_points = [(item[0], item[1]) for item in observed]
    area = _polygon_area(_convex_hull(image_points))
    if area <= 0.0:
        return 1.0 if observed else 0.0
    return min(1.0, area / float(image.width * image.height))


def _footprint_overlap_score(
    bounds: PatchBounds,
    image: SparseImage,
    observed: list[tuple[float, float, float, float, float]],
) -> float:
    if not observed:
        return 1.0 if bounds.contains_xy(image.center[0], image.center[1]) else 0.0
    xs = [item[2] for item in observed]
    ys = [item[3] for item in observed]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    overlap_w = max(0.0, min(max_x, bounds.max_x) - max(min_x, bounds.min_x))
    overlap_h = max(0.0, min(max_y, bounds.max_y) - max(min_y, bounds.min_y))
    patch_area = max(bounds.width * bounds.height, 1e-12)
    if overlap_w == 0.0 and overlap_h == 0.0 and any(bounds.contains_xy(x, y) for x, y in zip(xs, ys, strict=True)):
        return min(1.0, 1.0 / patch_area)
    return min(1.0, (overlap_w * overlap_h) / patch_area)


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
    point_by_id = _point_lookup(scene)
    track_counts: dict[int, int] = {}
    observed_by_image: dict[int, list[tuple[float, float, float, float, float]]] = {}
    candidate_images = [*internal_images, *external_images]

    for image in candidate_images:
        observed = _observed_patch_points(image, patch_point_ids, point_by_id)
        observed_by_image[image.image_id] = observed
        track_counts[image.image_id] = len({int(item[4]) for item in observed})

    positive_counts = [count for count in track_counts.values() if count > 0]
    median_visible_patch_track_count = _median([float(count) for count in positive_counts]) or 1.0
    centre_x, centre_y = bounds.centre
    internal_ids = {image.image_id for image in internal_images}

    scores: list[CameraSelectionScore] = []
    for image in candidate_images:
        observed = observed_by_image.get(image.image_id, [])
        visible_patch_track_count = track_counts.get(image.image_id, 0)
        normalised_track_score = min(1.0, visible_patch_track_count / median_visible_patch_track_count)
        footprint_overlap_score = _footprint_overlap_score(bounds, image, observed)
        target_image_share = _target_image_share(image, observed)
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
