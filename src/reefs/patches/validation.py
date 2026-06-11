"""Patch dataset validation helpers."""

from __future__ import annotations

from pathlib import Path

from reefs.io.yaml_json import read_json


def validate_patch_metadata(patch_dir: Path, *, max_cameras: int) -> dict[str, object]:
    """Validate one generated patch metadata file."""
    metadata = read_json(patch_dir / "patch_metadata.json")
    if not isinstance(metadata, dict):
        raise ValueError(f"Patch metadata must be a JSON object: {patch_dir}")
    selected = metadata.get("selected_images")
    if not isinstance(selected, list):
        raise ValueError(f"Patch metadata selected_images must be a list: {patch_dir}")
    selected_dir = patch_dir / "selected_images"
    missing = [name for name in selected if not (selected_dir / str(name)).exists()]
    invalid_reasons = list(metadata.get("invalid_reasons") or [])
    if missing:
        invalid_reasons.append("missing_selected_images")
    if int(metadata.get("selected_camera_count") or 0) > max_cameras:
        invalid_reasons.append("too_many_selected_cameras")
    if int(metadata.get("sparse_point_count") or 0) <= 0:
        invalid_reasons.append("no_sparse_points")
    required = [
        patch_dir / "sparse" / "0" / "cameras.txt",
        patch_dir / "sparse" / "0" / "images.txt",
        patch_dir / "sparse" / "0" / "points3D.txt",
        patch_dir / "patch_diagnostics" / "camera_coverage.csv",
        patch_dir / "patch_diagnostics" / "generation.log",
    ]
    missing_required = [str(path) for path in required if not path.exists()]
    if missing_required:
        invalid_reasons.append("missing_required_patch_artifacts")
    metadata["invalid_reasons"] = sorted(set(str(reason) for reason in invalid_reasons))
    metadata["status"] = "invalid" if metadata["invalid_reasons"] else "valid"
    if missing_required:
        metadata["missing_required_artifacts"] = missing_required
    return metadata
