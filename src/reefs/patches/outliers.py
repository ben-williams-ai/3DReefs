"""Camera pose outlier scoring and filtering helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from reefs.patches.artefacts import SparseImage, SparseScene


@dataclass(frozen=True)
class CameraOutlierRecord:
    """Outlier decision for one registered camera pose."""

    image_id: int
    image_name: str
    camera_center: tuple[float, float, float]
    method: str
    method_parameters: dict[str, object]
    score: float
    threshold: float
    decision: str
    reason: str

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable outlier record."""
        return {
            "image_id": self.image_id,
            "image_name": self.image_name,
            "camera_center": list(self.camera_center),
            "method": self.method,
            "method_parameters": self.method_parameters,
            "score": self.score,
            "threshold": self.threshold,
            "decision": self.decision,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class OutlierFilterResult:
    """Outlier filtering outcome for a sparse scene."""

    records: list[CameraOutlierRecord]
    removed_image_ids: set[int]
    kept_image_ids: set[int]
    state: str
    warnings: list[str]

    @property
    def removed_count(self) -> int:
        """Return removed camera count."""
        return len(self.removed_image_ids)

    @property
    def kept_count(self) -> int:
        """Return kept camera count."""
        return len(self.kept_image_ids)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable result."""
        return {
            "state": self.state,
            "removed_camera_count": self.removed_count,
            "kept_camera_count": self.kept_count,
            "removed_images": [
                record.image_name for record in self.records if record.image_id in self.removed_image_ids
            ],
            "warnings": self.warnings,
            "records": [record.as_dict() for record in self.records],
        }


def _iqr_bounds(values: np.ndarray, multiplier: float) -> tuple[np.ndarray, np.ndarray]:
    q1 = np.percentile(values, 25, axis=0)
    q3 = np.percentile(values, 75, axis=0)
    iqr = q3 - q1
    zero_iqr = iqr == 0
    iqr[zero_iqr] = np.maximum(np.std(values, axis=0)[zero_iqr], 1e-9)
    return q1 - multiplier * iqr, q3 + multiplier * iqr


def detect_camera_pose_outliers(
    scene: SparseScene,
    *,
    method: str,
    iqr_mult: float,
    percentile: float,
    max_removal_fraction: float,
    dry_run: bool,
) -> OutlierFilterResult:
    """Detect obvious camera-pose outliers from camera centres."""
    if not scene.images:
        raise ValueError("Cannot filter outliers without registered images")
    centres = np.array([image.center for image in scene.images], dtype=float)
    image_by_id = {image.image_id: image for image in scene.images}
    if method == "iqr":
        lower, upper = _iqr_bounds(centres.copy(), iqr_mult)
        outside = np.any((centres < lower) | (centres > upper), axis=1)
        distances = np.maximum.reduce([lower - centres, centres - upper, np.zeros_like(centres)])
        scores = np.linalg.norm(distances, axis=1)
        threshold = 0.0
        parameters = {"iqr_mult": iqr_mult}
    elif method == "percentile":
        median = np.median(centres, axis=0)
        scores = np.linalg.norm(centres - median, axis=1)
        threshold = float(np.percentile(scores, percentile))
        outside = scores > threshold
        parameters = {"percentile": percentile}
    else:
        raise ValueError(f"Unsupported outlier method: {method}")

    proposed_ids = {image.image_id for image, is_outside in zip(scene.images, outside) if bool(is_outside)}
    removal_fraction = len(proposed_ids) / len(scene.images)
    warnings: list[str] = []
    state = "complete_no_removals"
    final_removed: set[int] = set()
    if proposed_ids:
        if removal_fraction > max_removal_fraction:
            state = "blocked_ambiguous"
            warnings.append(
                f"Proposed removal fraction {removal_fraction:.3f} exceeds max_removal_fraction={max_removal_fraction:.3f}."
            )
        elif dry_run:
            state = "dry_run_reported"
        else:
            state = "complete_removed_outliers"
            final_removed = proposed_ids

    records: list[CameraOutlierRecord] = []
    for image, score, is_outside in zip(scene.images, scores, outside):
        if image.image_id in final_removed:
            decision = "removed"
        elif image.image_id in proposed_ids:
            decision = "proposed"
        else:
            decision = "kept"
        records.append(
            CameraOutlierRecord(
                image_id=image.image_id,
                image_name=image.name,
                camera_center=image.center,
                method=method,
                method_parameters=parameters,
                score=float(score),
                threshold=threshold,
                decision=decision,
                reason="outside_robust_camera_centre_bounds" if bool(is_outside) else "inside_bounds",
            )
        )
    kept_ids = set(image_by_id) - final_removed
    return OutlierFilterResult(
        records=records,
        removed_image_ids=final_removed,
        kept_image_ids=kept_ids,
        state=state,
        warnings=warnings,
    )
