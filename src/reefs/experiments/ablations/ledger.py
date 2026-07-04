"""Atomic CSV ledgers for ablation results."""

from __future__ import annotations

import csv
import os
import shutil
from pathlib import Path
from typing import Iterable

from reefs.experiments.ablations.time_utils import utc_now


STATUS_STATES = {
    "planned",
    "running",
    "complete",
    "complete_with_warnings",
    "failed",
    "superseded",
    "archived",
}

MANIFEST_FIELDS = [
    "job_id",
    "phase",
    "dataset",
    "variant",
    "patch_size",
    "splat_count",
    "max_width",
    "image_size",
    "feature_type",
    "mapper_backend",
    "matching_mode",
    "loop_detection",
    "vocab_tree_matcher",
    "guided_matching",
    "cross_camera_pairs",
    "cross_camera_matching_pass",
    "sparse_refinement",
    "intrinsics_refinement",
    "feature_max_image_size",
    "undistortion_max_image_size",
    "lfs_max_width",
    "baseline_diff",
    "status",
]

SFM_FIELDS = [
    "job_id",
    "dataset",
    "variant",
    "status",
    "sfm_runtime_seconds",
    "patch_runtime_seconds",
    "registered_images",
    "total_images",
    "registered_images_percent",
    "sparse_model_count",
    "selected_sparse_model_id",
    "selected_sparse_model_path",
    "selected_sparse_model_copy_path",
    "connected_components",
    "largest_component_images",
    "largest_component_percent",
    "mean_reprojection_error_px",
    "median_reprojection_error_px",
    "sparse_point_count",
    "mean_track_length",
    "median_track_length",
    "keypoint_image_count",
    "total_keypoints",
    "min_keypoints_per_image",
    "median_keypoints_per_image",
    "mean_keypoints_per_image",
    "max_keypoints_per_image",
    "verified_image_pairs",
    "cross_camera_verified_pairs",
    "selected_patches",
    "peak_ram_mib",
    "peak_vram_mib",
    "failure_reason",
    "updated_at",
]

SPLAT_FIELDS = [
    "job_id",
    "dataset",
    "variant",
    "patch_id",
    "patch_size",
    "splat_count",
    "max_width",
    "status",
    "ssim",
    "psnr",
    "lpips",
    "eval_target_source",
    "eval_image_width",
    "eval_image_height",
    "training_runtime_seconds",
    "output_ply_size_bytes",
    "output_sog_size_bytes",
    "actual_splat_count",
    "peak_ram_mib",
    "peak_vram_mib",
    "failure_reason",
    "updated_at",
]

METRICS_LONG_FIELDS = [
    "job_id",
    "dataset",
    "variant",
    "patch_id",
    "patch_size",
    "splat_count",
    "max_width",
    "attempt",
    "iteration",
    "psnr",
    "ssim",
    "lpips",
    "eval_target_source",
    "eval_image_width",
    "eval_image_height",
    "time_per_image",
    "num_gaussians",
    "metrics_path",
    "updated_at",
]

FINAL_FIELDS = [
    "job_id",
    "dataset",
    "variant",
    "status",
    "runtime_seconds",
    "merged_ply_size_bytes",
    "sog_size_bytes",
    "actual_splat_count",
    "failure_reason",
    "updated_at",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read rows from a CSV file, returning an empty list when absent."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    """Write a CSV atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})
    os.replace(tmp, path)


def upsert_row(path: Path, fieldnames: list[str], row: dict[str, object], *, key: str = "job_id") -> None:
    """Insert or replace one CSV row by key."""
    _validate_status(row)
    rows = read_rows(path)
    key_value = str(row[key])
    replaced = False
    backup_needed = False
    updated: list[dict[str, object]] = []
    for existing in rows:
        if str(existing.get(key)) == key_value:
            if str(existing.get("status", "")).startswith("complete") and dict(existing) != {
                name: str(row.get(name, "")) for name in fieldnames
            }:
                backup_needed = True
            updated.append(row)
            replaced = True
        else:
            updated.append(existing)
    if not replaced:
        updated.append(row)
    if backup_needed and path.exists():
        backup_dir = path.parent / "ledger_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = utc_now().replace(":", "").replace("+", "")
        shutil.copy2(path, backup_dir / f"{path.stem}_{key_value}_{timestamp}{path.suffix}")
    atomic_write_csv(path, fieldnames, updated)


def completed_job_ids(path: Path) -> set[str]:
    """Return job ids already marked complete."""
    return {row["job_id"] for row in read_rows(path) if str(row.get("status", "")).startswith("complete")}


def _validate_status(row: dict[str, object]) -> None:
    """Reject misspelled status states before they enter formal ledgers."""
    status = row.get("status")
    if status is None or status == "":
        return
    if str(status) not in STATUS_STATES:
        raise ValueError(f"unknown ablation status: {status}")
