"""Camera Selection V2 for splat patch generation."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from reefs.patches.artefacts import SparseImage, SparsePoint, SparseScene
from reefs.patches.bounds import PatchBounds
from reefs.patches.visibility import (
    CameraIntrinsics,
    TargetSample,
    build_target_samples,
    parse_camera_intrinsics,
    project_world_point,
    sparse_point_density_weights,
)


SELECTOR_NAME = "camera_selection_v2"
SELECTOR_VERSION = "3"
WARNING_THRESHOLDS = {
    "meaningful_target_coverage": 0.50,
    "small_target_share": 0.03,
}

_TARGET_GAIN_WEIGHT = 3.0
_TRACK_WEIGHT = 0.75
_GEOMETRY_WEIGHT = 0.75
_TARGET_SHARE_WEIGHT = 0.35
_VIEW_BIN_WEIGHT = 0.05
_SPILLOVER_WEIGHT = 0.20


@dataclass(frozen=True)
class CameraSelectionScore:
    """Camera score and diagnostic record for Camera Selection V2."""

    image_id: int
    image_name: str
    source_patch: str
    pool: str
    azimuth_sector: int
    azimuth_degrees: float
    visible_patch_points: int
    projected_target_area_ratio: float
    median_visible_depth: float
    camera_x: float
    camera_y: float
    camera_z: float
    selected: bool = False
    matched_track_score: float = 0.0
    geometric_visibility_score: float = 0.0
    target_image_share: float = 0.0
    new_target_sample_gain: float = 0.0
    view_direction_gain: float = 0.0
    spillover_penalty: float = 0.0
    selection_reason: str = ""
    rejection_reason: str = ""
    warning_flags: tuple[str, ...] = ()
    target_sample_ids: frozenset[int] = field(default_factory=frozenset)

    @property
    def local(self) -> bool:
        """Compatibility alias for old callers."""
        return self.pool == "internal"

    @property
    def total_visible_points(self) -> int:
        """Compatibility alias for old callers."""
        return self.visible_patch_points

    @property
    def core_visible_points(self) -> int:
        """Compatibility alias for old callers."""
        return self.visible_patch_points

    @property
    def score(self) -> float:
        """Return a compact scalar score for summaries."""
        return self.matched_track_score + self.geometric_visibility_score

    def ranking_tuple(self) -> tuple[float, float, float, float, str]:
        """Return deterministic ranking for diagnostics and legacy helpers."""
        return (
            -(self.matched_track_score + self.geometric_visibility_score),
            -self.target_image_share,
            -float(self.visible_patch_points),
            self.median_visible_depth,
            self.image_name,
        )

    def with_updates(self, **updates: object) -> "CameraSelectionScore":
        """Return this score with selected fields changed."""
        return CameraSelectionScore(**{**self.as_constructor_dict(), **updates})

    def with_selected(self, selected: bool) -> "CameraSelectionScore":
        """Return this score with selection state changed."""
        return self.with_updates(selected=selected)

    def as_constructor_dict(self) -> dict[str, object]:
        """Return constructor-compatible score data."""
        return {
            "image_id": self.image_id,
            "image_name": self.image_name,
            "source_patch": self.source_patch,
            "pool": self.pool,
            "azimuth_sector": self.azimuth_sector,
            "azimuth_degrees": self.azimuth_degrees,
            "visible_patch_points": self.visible_patch_points,
            "projected_target_area_ratio": self.projected_target_area_ratio,
            "median_visible_depth": self.median_visible_depth,
            "camera_x": self.camera_x,
            "camera_y": self.camera_y,
            "camera_z": self.camera_z,
            "selected": self.selected,
            "matched_track_score": self.matched_track_score,
            "geometric_visibility_score": self.geometric_visibility_score,
            "target_image_share": self.target_image_share,
            "new_target_sample_gain": self.new_target_sample_gain,
            "view_direction_gain": self.view_direction_gain,
            "spillover_penalty": self.spillover_penalty,
            "selection_reason": self.selection_reason,
            "rejection_reason": self.rejection_reason,
            "warning_flags": self.warning_flags,
            "target_sample_ids": self.target_sample_ids,
        }

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable diagnostic score."""
        return {
            "patch_id": "",
            "image_id": self.image_id,
            "image_name": self.image_name,
            "selection_role": "selected" if self.selected else "unselected",
            "camera_role": self.pool,
            "candidate_source": self.source_patch,
            "selection_reason": self.selection_reason,
            "rejection_reason": self.rejection_reason,
            "matched_track_score": self.matched_track_score,
            "geometric_visibility_score": self.geometric_visibility_score,
            "target_image_share": self.target_image_share,
            "new_target_sample_gain": self.new_target_sample_gain,
            "view_direction_gain": self.view_direction_gain,
            "spillover_penalty": self.spillover_penalty,
            "warning_flags": ";".join(self.warning_flags),
            "camera_x": self.camera_x,
            "camera_y": self.camera_y,
            "camera_z": self.camera_z,
            "visible_patch_points": self.visible_patch_points,
            "projected_target_area_ratio": self.projected_target_area_ratio,
            "median_visible_depth": self.median_visible_depth,
            "azimuth_sector": self.azimuth_sector,
        }


@dataclass(frozen=True)
class PatchSelection:
    """Selected images and diagnostics for one patch."""

    bounds: PatchBounds
    selected_images: list[SparseImage]
    local_images: list[SparseImage]
    support_images: list[SparseImage]
    patch_points: list[SparsePoint]
    camera_scores: list[CameraSelectionScore]
    warnings: list[str]
    neighbour_bounds: list[PatchBounds]
    selector: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable selection summary."""
        selected_ids = {image.image_id for image in self.selected_images}
        internal_ids = {image.image_id for image in self.local_images}
        external_ids = {image.image_id for image in self.support_images}
        return {
            "patch_id": self.bounds.patch_id,
            "selected_images": [image.name for image in self.selected_images],
            "selected_camera_count": len(self.selected_images),
            "selected_internal_count": len(selected_ids & internal_ids),
            "selected_external_count": len(selected_ids & external_ids),
            "sparse_point_count": len(self.patch_points),
            "selector": self.selector,
            "warnings": self.warnings,
        }


def selector_settings() -> dict[str, object]:
    """Return stable selector settings recorded in patch-affecting config."""
    return {
        "name": SELECTOR_NAME,
        "version": SELECTOR_VERSION,
        "target_cells_per_image": 5,
        "min_target_cells_per_patch": 4,
        "warning_thresholds": WARNING_THRESHOLDS,
        "weights": {
            "target_gain": _TARGET_GAIN_WEIGHT,
            "track": _TRACK_WEIGHT,
            "geometry": _GEOMETRY_WEIGHT,
            "target_share": _TARGET_SHARE_WEIGHT,
            "view_bin": _VIEW_BIN_WEIGHT,
            "spillover": _SPILLOVER_WEIGHT,
        },
    }


def selector_signature(*, patch_affecting_config: dict[str, object], source_sparse: str) -> str:
    """Return a stable selector-affecting signature."""
    payload = {
        "selector": selector_settings(),
        "patch_affecting_config": patch_affecting_config,
        "source_sparse": source_sparse,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
    return min(1.0, _polygon_area(_convex_hull(points)) / float(width * height))


def _median(values: list[float]) -> float:
    if not values:
        return float("inf")
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((percentile / 100.0) * (len(ordered) - 1)))))
    return ordered[index]


def _azimuth_sector(camera_x: float, camera_y: float, centre_x: float, centre_y: float) -> tuple[int, float]:
    angle = (math.degrees(math.atan2(camera_y - centre_y, camera_x - centre_x)) + 360.0) % 360.0
    return int(angle // 45.0) % 8, angle


def sort_scores(scores: Iterable[CameraSelectionScore]) -> list[CameraSelectionScore]:
    """Sort camera scores for stable diagnostics."""
    return sorted(scores, key=lambda score: score.ranking_tuple())


def balanced_sector_selection(scores: list[CameraSelectionScore], target_count: int) -> list[CameraSelectionScore]:
    """Return best scores spread over populated azimuth sectors."""
    if target_count <= 0:
        return []
    per_sector: dict[int, list[CameraSelectionScore]] = defaultdict(list)
    for score in sort_scores(scores):
        per_sector[score.azimuth_sector].append(score)

    selected: list[CameraSelectionScore] = []
    while len(selected) < target_count and any(per_sector.values()):
        sector = min(
            (key for key, value in per_sector.items() if value),
            key=lambda key: (len([score for score in selected if score.azimuth_sector == key]), key),
        )
        selected.append(per_sector[sector].pop(0))
    return selected


def _internal_images_for_bounds(scene: SparseScene, bounds: PatchBounds) -> list[SparseImage]:
    return [image for image in scene.images if bounds.contains_xy(image.center[0], image.center[1])]


def _source_patch_for_external(image: SparseImage, neighbours: list[PatchBounds]) -> str:
    for neighbour in neighbours:
        if neighbour.contains_xy(image.center[0], image.center[1]):
            return neighbour.patch_id
    return "direct_target_evidence"


def _normalise(value: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return min(1.0, max(0.0, value / denominator))


def _projection_evidence(
    *,
    image: SparseImage,
    intrinsics: CameraIntrinsics | None,
    target_samples: list[TargetSample],
) -> tuple[frozenset[int], list[tuple[float, float]], list[float]]:
    if intrinsics is None:
        return frozenset(), [], []
    sample_ids: set[int] = set()
    xy: list[tuple[float, float]] = []
    depths: list[float] = []
    for sample in target_samples:
        projected = project_world_point(image, intrinsics, sample.xyz)
        if projected is None:
            continue
        px, py, depth = projected
        sample_ids.add(sample.sample_id)
        xy.append((px, py))
        depths.append(depth)
    return frozenset(sample_ids), xy, depths


def _score_candidate_cameras(
    scene: SparseScene,
    bounds: PatchBounds,
    *,
    internal_images: list[SparseImage],
    neighbour_images: list[SparseImage],
    neighbours: list[PatchBounds],
    patch_points: list[SparsePoint],
    target_samples: list[TargetSample],
) -> list[CameraSelectionScore]:
    intrinsics = parse_camera_intrinsics(scene.cameras_text)
    internal_ids = {image.image_id for image in internal_images}
    neighbour_ids = {image.image_id for image in neighbour_images}
    candidate_by_id: dict[int, SparseImage] = {image.image_id: image for image in [*internal_images, *neighbour_images]}
    density_weights = sparse_point_density_weights(patch_points, bounds)
    observations_by_image = {image.image_id: image.observations for image in scene.images}
    image_by_id = scene.image_by_id

    track_seen: dict[int, set[int]] = defaultdict(set)
    weighted_tracks: dict[int, float] = defaultdict(float)
    track_xy: dict[int, list[tuple[float, float]]] = defaultdict(list)
    track_depths: dict[int, list[float]] = defaultdict(list)
    for point in patch_points:
        for image_id, point2d_idx in point.track_pairs:
            image = image_by_id.get(image_id)
            if image is None:
                continue
            candidate_by_id.setdefault(image_id, image)
            observations = observations_by_image.get(image_id, ())
            if point2d_idx < 0 or point2d_idx >= len(observations):
                continue
            observation = observations[point2d_idx]
            track_seen[image_id].add(point.point_id)
            weighted_tracks[image_id] += density_weights.get(point.point_id, 1.0)
            track_xy[image_id].append((float(observation.x), float(observation.y)))
            track_depths[image_id].append(float(math.dist(point.xyz, image.center)))

    target_total = max(1, len(target_samples))
    centre_x, centre_y = bounds.centre
    track_denominator = _percentile(list(weighted_tracks.values()), 95)

    projection_records: dict[int, tuple[frozenset[int], list[tuple[float, float]], list[float]]] = {}
    # Projection is the only way to find non-neighbour external cameras that still
    # genuinely see the patch footprint.
    for image in scene.images:
        record = _projection_evidence(
            image=image,
            intrinsics=intrinsics.get(image.camera_id),
            target_samples=target_samples,
        )
        if record[0]:
            projection_records[image.image_id] = record
            candidate_by_id.setdefault(image.image_id, image)

    scores: list[CameraSelectionScore] = []
    for image in candidate_by_id.values():
        projected_ids, projected_xy, projected_depths = projection_records.get(image.image_id, (frozenset(), [], []))
        track_score = _normalise(weighted_tracks[image.image_id], track_denominator)
        geometry_score = _normalise(float(len(projected_ids)), float(target_total))
        pool = "internal" if image.image_id in internal_ids else "external"
        source_patch = bounds.patch_id if pool == "internal" else _source_patch_for_external(image, neighbours)
        if pool == "external" and image.image_id not in neighbour_ids and not projected_ids and image.image_id not in track_seen:
            continue
        sector, angle = _azimuth_sector(image.center[0], image.center[1], centre_x, centre_y)
        fallback_intrinsics = intrinsics.get(image.camera_id, CameraIntrinsics(0, "", 1, 1, 1, 1, 0, 0))
        image_width = image.width or fallback_intrinsics.width
        image_height = image.height or fallback_intrinsics.height
        target_share = _projected_area_ratio(projected_xy, image_width, image_height)
        scores.append(
            CameraSelectionScore(
                image_id=image.image_id,
                image_name=image.name,
                source_patch=source_patch,
                pool=pool,
                azimuth_sector=sector,
                azimuth_degrees=angle,
                visible_patch_points=len(track_seen[image.image_id]),
                projected_target_area_ratio=_projected_area_ratio(track_xy[image.image_id], image_width, image_height),
                median_visible_depth=_median([*track_depths[image.image_id], *projected_depths]),
                camera_x=image.center[0],
                camera_y=image.center[1],
                camera_z=image.center[2],
                matched_track_score=track_score,
                geometric_visibility_score=geometry_score,
                target_image_share=target_share,
                target_sample_ids=projected_ids,
            )
        )
    return scores


def _typical_target_share(scores: list[CameraSelectionScore]) -> float:
    values = [score.target_image_share for score in scores if score.target_image_share > 0.0]
    return max(_percentile(values, 75), WARNING_THRESHOLDS["small_target_share"])


def _is_useful_candidate(score: CameraSelectionScore) -> bool:
    if score.matched_track_score > 0.0:
        return True
    return (
        score.geometric_visibility_score > 0.0
        and score.target_image_share >= WARNING_THRESHOLDS["small_target_share"]
    )


def _select_greedily(
    scores: list[CameraSelectionScore],
    *,
    max_cameras: int,
    target_samples: list[TargetSample],
) -> list[CameraSelectionScore]:
    target_total = max(1, len(target_samples))
    typical_share = _typical_target_share(scores)
    selected: list[CameraSelectionScore] = []
    remaining = list(scores)
    covered_target_samples: set[int] = set()
    covered_view_bins: set[int] = set()

    while remaining and len(selected) < max_cameras:
        best_index: int | None = None
        best_score: CameraSelectionScore | None = None
        best_tuple: tuple[float, float, float, float, int, int] | None = None
        for index, score in enumerate(remaining):
            new_target_ids = set(score.target_sample_ids) - covered_target_samples
            new_target_gain = len(new_target_ids) / target_total
            view_bin_gain = 1.0 / 8.0 if score.azimuth_sector not in covered_view_bins else 0.0
            share_ratio = min(1.0, score.target_image_share / typical_share) if typical_share > 0 else 1.0
            spillover_penalty = _SPILLOVER_WEIGHT * (1.0 - math.sqrt(max(0.0, share_ratio)))
            gain = (
                (_TARGET_GAIN_WEIGHT * new_target_gain)
                + (_TRACK_WEIGHT * score.matched_track_score)
                + (_GEOMETRY_WEIGHT * score.geometric_visibility_score)
                + (_TARGET_SHARE_WEIGHT * score.target_image_share)
                + (_VIEW_BIN_WEIGHT * view_bin_gain)
                - spillover_penalty
            )
            updated = score.with_updates(
                new_target_sample_gain=new_target_gain,
                view_direction_gain=view_bin_gain,
                spillover_penalty=spillover_penalty,
            )
            tie_breaker = (
                gain,
                score.matched_track_score + score.geometric_visibility_score,
                score.target_image_share,
                view_bin_gain,
                1 if score.pool == "internal" else 0,
                -score.image_id,
            )
            if best_tuple is None or tie_breaker > best_tuple:
                best_index = index
                best_score = updated
                best_tuple = tie_breaker
        if best_index is None or best_score is None:
            break
        remaining.pop(best_index)
        selected.append(best_score.with_updates(selected=True, selection_reason=f"marginal_gain={best_tuple[0]:.6f}"))
        covered_target_samples.update(best_score.target_sample_ids)
        covered_view_bins.add(best_score.azimuth_sector)
    return selected


def _selection_warnings(
    *,
    patch_points: list[SparsePoint],
    scores: list[CameraSelectionScore],
    selected_scores: list[CameraSelectionScore],
    target_samples: list[TargetSample],
    max_cameras: int,
) -> tuple[list[str], dict[str, float]]:
    selected_target_samples = set().union(*(score.target_sample_ids for score in selected_scores)) if selected_scores else set()
    view_bins = {score.azimuth_sector for score in selected_scores}
    selected_external = len([score for score in selected_scores if score.pool == "external"])
    external_fraction = selected_external / max(1, len(selected_scores))
    target_shares = [score.target_image_share for score in selected_scores]
    coverage = {
        "footprint": len(selected_target_samples) / max(1, len(target_samples)),
        "view_direction_bins": len(view_bins) / 8.0,
        "external_fraction": external_fraction,
        "median_target_image_share": _median(target_shares) if target_shares else 0.0,
        "min_target_image_share": min(target_shares) if target_shares else 0.0,
    }
    warnings: list[str] = []
    if not patch_points:
        warnings.append("No sparse points fall inside patch bounds.")
    if not scores:
        warnings.append("No candidate cameras were found for patch.")
    if scores and not selected_scores:
        warnings.append("No candidate cameras meaningfully covered the patch target.")
    if len(selected_scores) == max_cameras and len(scores) > max_cameras:
        warnings.append(f"Selection capped at max_cameras={max_cameras}.")
    if coverage["footprint"] < WARNING_THRESHOLDS["meaningful_target_coverage"]:
        warnings.append(f"Poor selector footprint coverage: {coverage['footprint']:.3f}.")
    if selected_scores and coverage["min_target_image_share"] < WARNING_THRESHOLDS["small_target_share"]:
        warnings.append(f"At least one selected camera has small target image share: {coverage['min_target_image_share']:.4f}.")
    return warnings, coverage


def _finalise_scores(
    scores: list[CameraSelectionScore],
    selected_scores: list[CameraSelectionScore],
) -> list[CameraSelectionScore]:
    selected_by_id = {score.image_id: score for score in selected_scores}
    final_scores: list[CameraSelectionScore] = []
    for score in scores:
        selected = selected_by_id.get(score.image_id)
        if selected:
            warning_flags: list[str] = []
            if selected.target_image_share < WARNING_THRESHOLDS["small_target_share"]:
                warning_flags.append("small_target_share")
            final_scores.append(selected.with_updates(warning_flags=tuple(warning_flags)))
        else:
            if score.matched_track_score <= 0.0 and score.geometric_visibility_score <= 0.0:
                reason = "no_target_evidence"
            elif score.target_image_share < WARNING_THRESHOLDS["small_target_share"] and score.matched_track_score <= 0.0:
                reason = "weak_target_sliver"
            else:
                reason = "lower_marginal_gain"
            final_scores.append(score.with_updates(selected=False, rejection_reason=reason))
    return sorted(final_scores, key=lambda item: (not item.selected, item.pool, item.image_name))


def select_patch_views(
    scene: SparseScene,
    bounds: PatchBounds,
    *,
    max_cameras: int,
    all_bounds: list[PatchBounds] | None = None,
) -> PatchSelection:
    """Select cameras using Camera Selection V2."""
    if max_cameras <= 0:
        raise ValueError("max_cameras must be positive")
    patch_points = [point for point in scene.points if bounds.contains_xy(point.xyz[0], point.xyz[1])]
    all_patch_bounds = all_bounds or [bounds]
    target_samples = build_target_samples(scene, bounds, patch_points, all_bounds=all_patch_bounds)
    neighbours = discover_one_ring_neighbours(all_patch_bounds, bounds)
    internal_images = _internal_images_for_bounds(scene, bounds)
    internal_ids = {image.image_id for image in internal_images}
    neighbour_by_id: dict[int, SparseImage] = {}
    for neighbour in neighbours:
        for image in _internal_images_for_bounds(scene, neighbour):
            if image.image_id not in internal_ids:
                neighbour_by_id.setdefault(image.image_id, image)
    neighbour_images = list(neighbour_by_id.values())
    scores = _score_candidate_cameras(
        scene,
        bounds,
        internal_images=internal_images,
        neighbour_images=neighbour_images,
        neighbours=neighbours,
        patch_points=patch_points,
        target_samples=target_samples,
    )
    selectable = [score for score in scores if _is_useful_candidate(score)]
    selected_scores = _select_greedily(selectable, max_cameras=max_cameras, target_samples=target_samples)
    camera_scores = _finalise_scores(scores, selected_scores)
    selected_ids = {score.image_id for score in selected_scores}
    selected_images = [scene.image_by_id[image_id] for image_id in selected_ids if image_id in scene.image_by_id]
    selected_images.sort(key=lambda image: image.image_id)
    warnings, coverage = _selection_warnings(
        patch_points=patch_points,
        scores=scores,
        selected_scores=selected_scores,
        target_samples=target_samples,
        max_cameras=max_cameras,
    )
    selector = {
        "name": SELECTOR_NAME,
        "version": SELECTOR_VERSION,
        "target_sample_count": len(target_samples),
        "scene_registered_image_count": len(scene.images),
        "scene_target_cell_count": round(len(scene.images) / 5),
        "patch_target_cell_count": len({sample.cell_id.rsplit(":", 1)[0] for sample in target_samples}),
        "grid_x_count": len({sample.cell_id.split(":")[0] for sample in target_samples}),
        "grid_y_count": len({sample.cell_id.split(":")[1] for sample in target_samples}),
        "coverage": {
            "footprint": coverage["footprint"],
            "view_direction_bins": coverage["view_direction_bins"],
        },
        "target_image_share": {
            "median_selected": coverage["median_target_image_share"],
            "min_selected": coverage["min_target_image_share"],
        },
        "warning_thresholds": WARNING_THRESHOLDS,
        "warnings": warnings,
    }
    return PatchSelection(
        bounds=bounds,
        selected_images=selected_images,
        local_images=internal_images,
        support_images=[score_image for score_image in scene.images if score_image.image_id in {s.image_id for s in scores if s.pool == "external"}],
        patch_points=patch_points,
        camera_scores=camera_scores,
        warnings=warnings,
        neighbour_bounds=neighbours,
        selector=selector,
    )
