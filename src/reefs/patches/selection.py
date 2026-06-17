"""Target-aware spatial greedy camera selection helpers."""

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
    local_position_cell,
    parse_camera_intrinsics,
    project_world_point,
    sparse_point_density_weights,
)


SELECTOR_NAME = "target_aware_spatial_greedy"
SELECTOR_VERSION = "2"
WARNING_THRESHOLDS = {
    "meaningful_target_coverage": 0.50,
    "small_target_share": 0.03,
    "excessive_support_fraction": 0.50,
}

_BODY_WEIGHT = 3.0
_BOUNDARY_WEIGHT = 2.0
_LOCAL_CELL_WEIGHT = 0.45
_VIEW_BIN_WEIGHT = 0.10
_STATIC_VISIBILITY_WEIGHT = 0.25
_SPILLOVER_WEIGHT = 0.20
_NONLOCAL_BASE_PENALTY = 0.03
_NONLOCAL_SHARE_PENALTY = 0.08


@dataclass(frozen=True)
class CameraSelectionScore:
    """Camera score and diagnostic record for patch selection."""

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
    track_body_score: float = 0.0
    track_boundary_score: float = 0.0
    projection_body_score: float = 0.0
    projection_boundary_score: float = 0.0
    hybrid_body_score: float = 0.0
    hybrid_boundary_score: float = 0.0
    target_image_share: float = 0.0
    new_body_sample_gain: float = 0.0
    new_boundary_sample_gain: float = 0.0
    new_local_cell_gain: float = 0.0
    view_bin_gain: float = 0.0
    nonlocal_penalty: float = 0.0
    spillover_penalty: float = 0.0
    selection_reason: str = ""
    rejection_reason: str = ""
    warning_flags: tuple[str, ...] = ()
    local_cell_id: str | None = None
    body_sample_ids: frozenset[int] = field(default_factory=frozenset)
    boundary_sample_ids: frozenset[int] = field(default_factory=frozenset)

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
        """Return a coarse scalar score for summaries."""
        return self.hybrid_body_score + self.hybrid_boundary_score

    def ranking_tuple(self) -> tuple[float, float, float, float, float, str]:
        """Return deterministic legacy-compatible ranking tuple."""
        return (
            -float(self.boundary_visible_points),
            -float(self.projected_boundary_area_ratio),
            -float(self.core_visible_points),
            -float(self.projected_core_area_ratio),
            float(self.median_visible_depth),
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
            "track_body_score": self.track_body_score,
            "track_boundary_score": self.track_boundary_score,
            "projection_body_score": self.projection_body_score,
            "projection_boundary_score": self.projection_boundary_score,
            "hybrid_body_score": self.hybrid_body_score,
            "hybrid_boundary_score": self.hybrid_boundary_score,
            "target_image_share": self.target_image_share,
            "new_body_sample_gain": self.new_body_sample_gain,
            "new_boundary_sample_gain": self.new_boundary_sample_gain,
            "new_local_cell_gain": self.new_local_cell_gain,
            "view_bin_gain": self.view_bin_gain,
            "nonlocal_penalty": self.nonlocal_penalty,
            "spillover_penalty": self.spillover_penalty,
            "selection_reason": self.selection_reason,
            "rejection_reason": self.rejection_reason,
            "warning_flags": self.warning_flags,
            "local_cell_id": self.local_cell_id,
            "body_sample_ids": self.body_sample_ids,
            "boundary_sample_ids": self.boundary_sample_ids,
        }

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable diagnostic score."""
        return {
            "patch_id": "",
            "image_id": self.image_id,
            "image_name": self.image_name,
            "selection_role": "selected" if self.selected else "unselected",
            "pool": self.pool,
            "source_patch": self.source_patch,
            "selection_reason": self.selection_reason,
            "rejection_reason": self.rejection_reason,
            "hybrid_body_score": self.hybrid_body_score,
            "hybrid_boundary_score": self.hybrid_boundary_score,
            "track_body_score": self.track_body_score,
            "track_boundary_score": self.track_boundary_score,
            "projection_body_score": self.projection_body_score,
            "projection_boundary_score": self.projection_boundary_score,
            "target_image_share": self.target_image_share,
            "new_body_sample_gain": self.new_body_sample_gain,
            "new_boundary_sample_gain": self.new_boundary_sample_gain,
            "new_local_cell_gain": self.new_local_cell_gain,
            "view_bin_gain": self.view_bin_gain,
            "nonlocal_penalty": self.nonlocal_penalty,
            "spillover_penalty": self.spillover_penalty,
            "warning_flags": ";".join(self.warning_flags),
            "camera_x": self.camera_x,
            "camera_y": self.camera_y,
            "camera_z": self.camera_z,
            # Legacy columns retained for older diagnostics/tests.
            "core_projection_portion": self.projected_interior_area_ratio,
            "boundary_projection_area": self.projected_boundary_area_ratio,
            "combined_projection_portion": self.projected_core_area_ratio,
            "core_visible_points": self.interior_visible_points,
            "boundary_visible_points": self.boundary_visible_points,
            "combined_visible_points": self.core_visible_points,
            "median_visible_depth": self.median_visible_depth,
            "azimuth_sector": self.azimuth_sector,
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
    selector: dict[str, object] = field(default_factory=dict)

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
        "density_grid_size": 10,
        "local_position_grid_size": 10,
        "warning_thresholds": WARNING_THRESHOLDS,
        "weights": {
            "body": _BODY_WEIGHT,
            "boundary": _BOUNDARY_WEIGHT,
            "local_cell": _LOCAL_CELL_WEIGHT,
            "view_bin": _VIEW_BIN_WEIGHT,
            "static_visibility": _STATIC_VISIBILITY_WEIGHT,
            "spillover": _SPILLOVER_WEIGHT,
            "nonlocal_base": _NONLOCAL_BASE_PENALTY,
            "nonlocal_share": _NONLOCAL_SHARE_PENALTY,
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
    """Legacy helper retained for old tests and comparison scripts."""
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


def _source_patch_for_support(image: SparseImage, neighbours: list[PatchBounds]) -> str:
    for neighbour in neighbours:
        if neighbour.contains_xy(image.center[0], image.center[1]):
            return neighbour.patch_id
    return "target_observer"


def _normalise(value: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return min(1.0, max(0.0, value / denominator))


def _projection_evidence(
    *,
    image: SparseImage,
    intrinsics: CameraIntrinsics | None,
    target_samples: list[TargetSample],
) -> tuple[frozenset[int], frozenset[int], list[tuple[float, float]], list[float]]:
    if intrinsics is None:
        return frozenset(), frozenset(), [], []
    body: set[int] = set()
    boundary: set[int] = set()
    xy: list[tuple[float, float]] = []
    depths: list[float] = []
    for sample in target_samples:
        projected = project_world_point(image, intrinsics, sample.xyz)
        if projected is None:
            continue
        px, py, depth = projected
        xy.append((px, py))
        depths.append(depth)
        if sample.role == "boundary":
            boundary.add(sample.sample_id)
        else:
            body.add(sample.sample_id)
    return frozenset(body), frozenset(boundary), xy, depths


def _score_candidate_cameras(
    scene: SparseScene,
    bounds: PatchBounds,
    *,
    local_images: list[SparseImage],
    support_images: list[SparseImage],
    neighbours: list[PatchBounds],
    patch_points: list[SparsePoint],
    target_samples: list[TargetSample],
) -> list[CameraSelectionScore]:
    intrinsics = parse_camera_intrinsics(scene.cameras_text)
    local_ids = {image.image_id for image in local_images}
    support_ids = {image.image_id for image in support_images}
    candidate_by_id: dict[int, SparseImage] = {image.image_id: image for image in [*local_images, *support_images]}
    patch_point_by_id = {point.point_id: point for point in patch_points}
    density_weights = sparse_point_density_weights(patch_points, bounds)
    observations_by_image = {image.image_id: image.observations for image in scene.images}
    image_by_id = scene.image_by_id

    track_seen: dict[int, dict[str, set[int]]] = defaultdict(lambda: {"body": set(), "boundary": set()})
    weighted_tracks: dict[int, dict[str, float]] = defaultdict(lambda: {"body": 0.0, "boundary": 0.0})
    track_xy: dict[int, dict[str, list[tuple[float, float]]]] = defaultdict(lambda: {"body": [], "boundary": [], "all": []})
    track_depths: dict[int, list[float]] = defaultdict(list)
    for point in patch_points:
        role = "boundary" if bounds.is_boundary_xy(point.xyz[0], point.xyz[1]) else "body"
        for image_id, point2d_idx in point.track_pairs:
            image = image_by_id.get(image_id)
            if image is None:
                continue
            candidate_by_id.setdefault(image_id, image)
            observations = observations_by_image.get(image_id, ())
            if point2d_idx < 0 or point2d_idx >= len(observations):
                continue
            observation = observations[point2d_idx]
            track_seen[image_id][role].add(point.point_id)
            weight = density_weights.get(point.point_id, 1.0)
            weighted_tracks[image_id][role] += weight
            xy = (float(observation.x), float(observation.y))
            track_xy[image_id][role].append(xy)
            track_xy[image_id]["all"].append(xy)
            track_depths[image_id].append(float(math.dist(point.xyz, image.center)))

    body_total = len([sample for sample in target_samples if sample.role == "body"])
    boundary_total = len(target_samples) - body_total
    centre_x, centre_y = bounds.centre
    body_track_denominator = _percentile([scores["body"] for scores in weighted_tracks.values()], 95)
    boundary_track_denominator = _percentile([scores["boundary"] for scores in weighted_tracks.values()], 95)

    projection_records: dict[int, tuple[frozenset[int], frozenset[int], list[tuple[float, float]], list[float]]] = {}
    for image in candidate_by_id.values():
        record = _projection_evidence(
            image=image,
            intrinsics=intrinsics.get(image.camera_id),
            target_samples=target_samples,
        )
        if record[0] or record[1]:
            projection_records[image.image_id] = record

    scores: list[CameraSelectionScore] = []
    for image in candidate_by_id.values():
        projected_body, projected_boundary, projected_xy, projected_depths = projection_records.get(
            image.image_id, (frozenset(), frozenset(), [], [])
        )
        track_body = _normalise(weighted_tracks[image.image_id]["body"], body_track_denominator)
        track_boundary = _normalise(weighted_tracks[image.image_id]["boundary"], boundary_track_denominator)
        projection_body = _normalise(float(len(projected_body)), float(body_total))
        projection_boundary = _normalise(float(len(projected_boundary)), float(boundary_total))
        hybrid_body = 1.0 - ((1.0 - track_body) * (1.0 - projection_body))
        hybrid_boundary = 1.0 - ((1.0 - track_boundary) * (1.0 - projection_boundary))
        pool = "local" if image.image_id in local_ids else "support" if image.image_id in support_ids else "target_observer"
        source_patch = bounds.patch_id if pool == "local" else _source_patch_for_support(image, neighbours)
        sector, angle = _azimuth_sector(image.center[0], image.center[1], centre_x, centre_y)
        image_width = image.width or intrinsics.get(image.camera_id, CameraIntrinsics(0, "", 1, 1, 1, 1, 0, 0)).width
        image_height = image.height or intrinsics.get(image.camera_id, CameraIntrinsics(0, "", 1, 1, 1, 1, 0, 0)).height
        target_share = _projected_area_ratio(projected_xy, image_width, image_height)
        body_point_ids = track_seen[image.image_id]["body"]
        boundary_point_ids = track_seen[image.image_id]["boundary"]
        scores.append(
            CameraSelectionScore(
                image_id=image.image_id,
                image_name=image.name,
                source_patch=source_patch,
                pool=pool,
                azimuth_sector=sector,
                azimuth_degrees=angle,
                core_visible_points=len(body_point_ids | boundary_point_ids),
                boundary_visible_points=len(boundary_point_ids),
                interior_visible_points=len(body_point_ids),
                projected_core_area_ratio=_projected_area_ratio(track_xy[image.image_id]["all"], image_width, image_height),
                projected_boundary_area_ratio=_projected_area_ratio(
                    track_xy[image.image_id]["boundary"], image_width, image_height
                ),
                projected_interior_area_ratio=_projected_area_ratio(track_xy[image.image_id]["body"], image_width, image_height),
                median_visible_depth=_median([*track_depths[image.image_id], *projected_depths]),
                camera_x=image.center[0],
                camera_y=image.center[1],
                camera_z=image.center[2],
                track_body_score=track_body,
                track_boundary_score=track_boundary,
                projection_body_score=projection_body,
                projection_boundary_score=projection_boundary,
                hybrid_body_score=hybrid_body,
                hybrid_boundary_score=hybrid_boundary,
                target_image_share=target_share,
                local_cell_id=local_position_cell(image, bounds),
                body_sample_ids=projected_body,
                boundary_sample_ids=projected_boundary,
            )
        )
    return scores


def _typical_target_share(scores: list[CameraSelectionScore]) -> float:
    values = [score.target_image_share for score in scores if score.target_image_share > 0.0]
    return max(_percentile(values, 75), WARNING_THRESHOLDS["small_target_share"])


def _purity_weight(score: CameraSelectionScore, typical_share: float) -> float:
    if typical_share <= 0.0:
        return 1.0
    return math.sqrt(min(1.0, max(0.0, score.target_image_share / typical_share)))


def _is_useful_candidate(score: CameraSelectionScore) -> bool:
    return (
        score.core_visible_points > 0
        or score.target_image_share >= WARNING_THRESHOLDS["small_target_share"]
        or score.hybrid_body_score >= WARNING_THRESHOLDS["meaningful_target_coverage"]
        or score.hybrid_boundary_score >= WARNING_THRESHOLDS["meaningful_target_coverage"]
    )


def _select_greedily(
    scores: list[CameraSelectionScore],
    *,
    max_cameras: int,
    target_samples: list[TargetSample],
) -> list[CameraSelectionScore]:
    body_total = max(1, len([sample for sample in target_samples if sample.role == "body"]))
    boundary_total = max(1, len(target_samples) - body_total)
    local_cells = {score.local_cell_id for score in scores if score.pool == "local" and score.local_cell_id}
    typical_share = _typical_target_share(scores)
    selected: list[CameraSelectionScore] = []
    remaining = list(scores)
    covered_body: set[int] = set()
    covered_boundary: set[int] = set()
    covered_cells: set[str] = set()
    covered_view_bins: set[int] = set()

    while remaining and len(selected) < max_cameras:
        selected_nonlocal = len([score for score in selected if score.pool != "local"])
        selected_nonlocal_fraction = selected_nonlocal / max(1, len(selected))
        best_index: int | None = None
        best_score: CameraSelectionScore | None = None
        best_gain = float("-inf")
        for index, score in enumerate(remaining):
            new_body_ids = set(score.body_sample_ids) - covered_body
            new_boundary_ids = set(score.boundary_sample_ids) - covered_boundary
            new_body_gain = len(new_body_ids) / body_total
            new_boundary_gain = len(new_boundary_ids) / boundary_total
            new_local_cell_gain = (
                (1.0 / max(1, len(local_cells)))
                if score.pool == "local" and score.local_cell_id and score.local_cell_id not in covered_cells
                else 0.0
            )
            view_bin_gain = 1.0 / 8.0 if score.azimuth_sector not in covered_view_bins else 0.0
            purity_weight = _purity_weight(score, typical_share)
            spillover_penalty = _SPILLOVER_WEIGHT * (1.0 - purity_weight)
            nonlocal_penalty = (
                _NONLOCAL_BASE_PENALTY + (_NONLOCAL_SHARE_PENALTY * selected_nonlocal_fraction)
                if score.pool != "local"
                else 0.0
            )
            gain = (
                (_BODY_WEIGHT * new_body_gain)
                + (_BOUNDARY_WEIGHT * new_boundary_gain)
                + (_LOCAL_CELL_WEIGHT * new_local_cell_gain)
                + (_VIEW_BIN_WEIGHT * view_bin_gain)
                + (_STATIC_VISIBILITY_WEIGHT * (score.hybrid_body_score + score.hybrid_boundary_score))
                - spillover_penalty
                - nonlocal_penalty
            )
            updated = score.with_updates(
                new_body_sample_gain=new_body_gain,
                new_boundary_sample_gain=new_boundary_gain,
                new_local_cell_gain=new_local_cell_gain,
                view_bin_gain=view_bin_gain,
                spillover_penalty=spillover_penalty,
                nonlocal_penalty=nonlocal_penalty,
            )
            tie_breaker = (
                gain,
                score.hybrid_body_score + score.hybrid_boundary_score,
                1 if score.pool == "local" else 0,
                score.target_image_share,
                -score.image_id,
            )
            best_tie = (
                best_gain,
                (best_score.hybrid_body_score + best_score.hybrid_boundary_score) if best_score else -1.0,
                1 if best_score and best_score.pool == "local" else 0,
                best_score.target_image_share if best_score else -1.0,
                -best_score.image_id if best_score else 0,
            )
            if best_index is None or tie_breaker > best_tie:
                best_index = index
                best_score = updated
                best_gain = gain
        if best_index is None or best_score is None:
            break
        remaining.pop(best_index)
        selected.append(best_score.with_updates(selected=True, selection_reason=f"marginal_gain={best_gain:.6f}"))
        covered_body.update(best_score.body_sample_ids)
        covered_boundary.update(best_score.boundary_sample_ids)
        if best_score.local_cell_id:
            covered_cells.add(best_score.local_cell_id)
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
    selected_body = set().union(*(score.body_sample_ids for score in selected_scores)) if selected_scores else set()
    selected_boundary = set().union(*(score.boundary_sample_ids for score in selected_scores)) if selected_scores else set()
    body_total = max(1, len([sample for sample in target_samples if sample.role == "body"]))
    boundary_total = max(1, len(target_samples) - body_total)
    local_cells = {score.local_cell_id for score in scores if score.pool == "local" and score.local_cell_id}
    selected_local_cells = {score.local_cell_id for score in selected_scores if score.pool == "local" and score.local_cell_id}
    view_bins = {score.azimuth_sector for score in selected_scores}
    selected_support = len([score for score in selected_scores if score.pool != "local"])
    support_fraction = selected_support / max(1, len(selected_scores))
    target_shares = [score.target_image_share for score in selected_scores]
    coverage = {
        "body": len(selected_body) / body_total,
        "boundary": len(selected_boundary) / boundary_total,
        "local_position_cells": len(selected_local_cells) / max(1, len(local_cells)),
        "view_bins": len(view_bins) / 8.0,
        "support_fraction": support_fraction,
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
    if coverage["body"] < WARNING_THRESHOLDS["meaningful_target_coverage"]:
        warnings.append(f"Poor selector body coverage: {coverage['body']:.3f}.")
    if coverage["boundary"] < WARNING_THRESHOLDS["meaningful_target_coverage"]:
        warnings.append(f"Poor selector boundary coverage: {coverage['boundary']:.3f}.")
    if local_cells and coverage["local_position_cells"] < 0.95:
        warnings.append(f"Local acquisition cell coverage below target: {coverage['local_position_cells']:.3f}.")
    if coverage["support_fraction"] > WARNING_THRESHOLDS["excessive_support_fraction"]:
        warnings.append(f"High support/nonlocal camera fraction: {coverage['support_fraction']:.3f}.")
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
            if score.hybrid_body_score <= 0.0 and score.hybrid_boundary_score <= 0.0:
                reason = "no_target_evidence"
            elif score.target_image_share < WARNING_THRESHOLDS["small_target_share"]:
                reason = "weak_target"
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
    """Select cameras with the Target-Aware Spatial Greedy selector."""
    if max_cameras <= 0:
        raise ValueError("max_cameras must be positive")
    patch_points = [point for point in scene.points if bounds.contains_xy(point.xyz[0], point.xyz[1])]
    all_patch_bounds = all_bounds or [bounds]
    target_samples = build_target_samples(scene, bounds, patch_points, all_bounds=all_patch_bounds)
    neighbours = discover_one_ring_neighbours(all_patch_bounds, bounds)
    local_images = _local_images_for_bounds(scene, bounds)
    support_by_id: dict[int, SparseImage] = {}
    local_ids = {image.image_id for image in local_images}
    for neighbour in neighbours:
        for image in _local_images_for_bounds(scene, neighbour):
            if image.image_id in local_ids:
                continue
            support_by_id.setdefault(image.image_id, image)
    support_images = list(support_by_id.values())
    scores = _score_candidate_cameras(
        scene,
        bounds,
        local_images=local_images,
        support_images=support_images,
        neighbours=neighbours,
        patch_points=patch_points,
        target_samples=target_samples,
    )
    selectable = [
        score
        for score in scores
        if (score.hybrid_body_score > 0.0 or score.hybrid_boundary_score > 0.0) and _is_useful_candidate(score)
    ]
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
        "target_cell_count": len({sample.cell_id.rsplit(":", 1)[0] for sample in target_samples}),
        "body_sample_count": len([sample for sample in target_samples if sample.role == "body"]),
        "boundary_sample_count": len([sample for sample in target_samples if sample.role == "boundary"]),
        "coverage": {
            key: value
            for key, value in coverage.items()
            if key in {"body", "boundary", "local_position_cells", "view_bins"}
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
        local_images=local_images,
        support_images=support_images,
        patch_points=patch_points,
        camera_scores=camera_scores,
        warnings=warnings,
        neighbour_bounds=neighbours,
        selector=selector,
    )
