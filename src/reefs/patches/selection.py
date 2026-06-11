"""View-based camera scoring and selection helpers."""

from __future__ import annotations

from dataclasses import dataclass

from reefs.patches.artefacts import SparseImage, SparsePoint, SparseScene
from reefs.patches.bounds import PatchBounds


@dataclass(frozen=True)
class CameraSelectionScore:
    """Camera score used for view-based patch selection."""

    image_id: int
    image_name: str
    local: bool
    visible_patch_points: int
    total_visible_points: int
    score: float
    selected: bool

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable score."""
        return {
            "image_id": self.image_id,
            "image_name": self.image_name,
            "local": self.local,
            "visible_patch_points": self.visible_patch_points,
            "total_visible_points": self.total_visible_points,
            "score": self.score,
            "selected": self.selected,
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

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable selection summary."""
        return {
            "patch_id": self.bounds.patch_id,
            "selected_images": [image.name for image in self.selected_images],
            "selected_camera_count": len(self.selected_images),
            "selected_local_count": len([image for image in self.selected_images if image in self.local_images]),
            "selected_support_count": len([image for image in self.selected_images if image in self.support_images]),
            "sparse_point_count": len(self.patch_points),
            "warnings": self.warnings,
        }


def select_patch_views(
    scene: SparseScene,
    bounds: PatchBounds,
    *,
    max_cameras: int,
) -> PatchSelection:
    """Select the best cameras for a patch using sparse point visibility."""
    if max_cameras <= 0:
        raise ValueError("max_cameras must be positive")
    patch_points = [point for point in scene.points if bounds.contains_point(point.xyz)]
    patch_point_ids_by_image: dict[int, set[int]] = {}
    total_point_ids_by_image: dict[int, set[int]] = {}
    for point in scene.points:
        for image_id in point.track_image_ids:
            total_point_ids_by_image.setdefault(image_id, set()).add(point.point_id)
    for point in patch_points:
        for image_id in point.track_image_ids:
            patch_point_ids_by_image.setdefault(image_id, set()).add(point.point_id)

    local_images = [image for image in scene.images if bounds.contains_point(image.center)]
    support_images = [
        scene.image_by_id[image_id]
        for image_id in patch_point_ids_by_image
        if image_id in scene.image_by_id
    ]
    candidate_ids = {image.image_id for image in local_images} | {image.image_id for image in support_images}
    warnings: list[str] = []
    if not patch_points:
        warnings.append("No sparse points fall inside patch bounds.")
    if not candidate_ids:
        warnings.append("No local or supporting cameras were found for patch.")

    scored: list[tuple[float, SparseImage]] = []
    for image in scene.images:
        visible_patch_points = len(patch_point_ids_by_image.get(image.image_id, set()))
        total_visible_points = len(total_point_ids_by_image.get(image.image_id, set()))
        local_bonus = 1.0 if image.image_id in {item.image_id for item in local_images} else 0.0
        if image.image_id not in candidate_ids:
            score = 0.0
        else:
            score = float(visible_patch_points) + local_bonus
        scored.append((score, image))

    selected = [
        image
        for score, image in sorted(scored, key=lambda item: (-item[0], item[1].center[0], item[1].name))
        if score > 0
    ][:max_cameras]
    selected_ids = {image.image_id for image in selected}
    camera_scores = [
        CameraSelectionScore(
            image_id=image.image_id,
            image_name=image.name,
            local=image.image_id in {item.image_id for item in local_images},
            visible_patch_points=len(patch_point_ids_by_image.get(image.image_id, set())),
            total_visible_points=len(total_point_ids_by_image.get(image.image_id, set())),
            score=score,
            selected=image.image_id in selected_ids,
        )
        for score, image in sorted(scored, key=lambda item: item[1].name)
    ]
    if len(selected) == max_cameras and len([score for score, _ in scored if score > 0]) > max_cameras:
        warnings.append(f"Selection capped at max_cameras={max_cameras}.")
    return PatchSelection(
        bounds=bounds,
        selected_images=selected,
        local_images=local_images,
        support_images=support_images,
        patch_points=patch_points,
        camera_scores=camera_scores,
        warnings=warnings,
    )
