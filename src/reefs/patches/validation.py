"""Patch dataset validation helpers."""

from __future__ import annotations

from pathlib import Path

from reefs.io.yaml_json import read_json
from reefs.patches.selection import SELECTOR_NAME


def validate_patch_metadata(patch_dir: Path, *, max_cameras: int) -> dict[str, object]:
    """Validate one generated patch metadata file."""
    metadata = read_json(patch_dir / "patch_metadata.json")
    if not isinstance(metadata, dict):
        raise ValueError(f"Patch metadata must be a JSON object: {patch_dir}")
    selected = metadata.get("selected_images")
    if not isinstance(selected, list):
        raise ValueError(f"Patch metadata selected_images must be a list: {patch_dir}")
    bounds = metadata.get("bounds")
    if not isinstance(bounds, dict):
        raise ValueError(f"Patch metadata must contain canonical nested bounds: {patch_dir}")
    required_bounds = ["min_x", "max_x", "min_y", "max_y", "min_z", "max_z", "buffer"]
    missing_bounds = [key for key in required_bounds if key not in bounds]
    if missing_bounds:
        raise ValueError(
            f"Patch metadata bounds missing required keys for {patch_dir}: " + ", ".join(missing_bounds)
        )
    try:
        numeric_bounds = {key: float(bounds[key]) for key in required_bounds}
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Patch metadata bounds must be numeric: {patch_dir}") from exc
    if numeric_bounds["min_x"] >= numeric_bounds["max_x"] or numeric_bounds["min_y"] >= numeric_bounds["max_y"]:
        raise ValueError(f"Patch metadata X/Y bounds are invalid: {patch_dir}")
    if numeric_bounds["min_z"] >= numeric_bounds["max_z"]:
        raise ValueError(f"Patch metadata Z bounds are invalid: {patch_dir}")
    selector = metadata.get("selector")
    if not isinstance(selector, dict):
        raise ValueError(f"Patch metadata must contain selector diagnostics: {patch_dir}")
    if selector.get("name") != SELECTOR_NAME:
        raise ValueError(f"Patch metadata selector.name must be {SELECTOR_NAME}: {patch_dir}")
    for key in ["version", "signature", "coverage", "warning_thresholds"]:
        if key not in selector:
            raise ValueError(f"Patch metadata selector missing required key {key}: {patch_dir}")
    coverage = selector.get("coverage")
    if not isinstance(coverage, dict):
        raise ValueError(f"Patch metadata selector.coverage must be an object: {patch_dir}")
    if not isinstance(selector.get("warning_thresholds"), dict):
        raise ValueError(f"Patch metadata selector.warning_thresholds must be an object: {patch_dir}")
    required_coverage = [
        "selected_internal_count",
        "rejected_internal_count",
        "selected_external_count",
        "unused_external_count",
        "max_cameras",
        "external_support_fraction",
        "external_support_allowance",
        "internal_patch_target",
    ]
    missing_coverage = [key for key in required_coverage if key not in coverage]
    if missing_coverage:
        raise ValueError(
            f"Patch metadata selector.coverage missing required keys for {patch_dir}: "
            + ", ".join(missing_coverage)
        )
    selected_dir = patch_dir / "selected_images"
    missing = [name for name in selected if not (selected_dir / str(name)).exists()]
    invalid_reasons = list(metadata.get("invalid_reasons") or [])
    if missing:
        invalid_reasons.append("missing_selected_images")
    if int(metadata.get("selected_camera_count") or 0) > max_cameras:
        invalid_reasons.append("too_many_selected_cameras")
    if int(coverage.get("selected_external_count") or 0) > int(coverage.get("external_support_allowance") or 0):
        invalid_reasons.append("too_many_external_support_cameras")
    if int(coverage.get("selected_internal_count") or 0) > max_cameras:
        invalid_reasons.append("useful_internal_count_exceeds_max_cameras")
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
