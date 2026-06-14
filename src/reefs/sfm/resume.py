"""SfM resume/status helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from reefs.colmap.outputs import list_sparse_models, select_sparse_model
from reefs.preflight.images import IMAGE_SUFFIXES


def sfm_step_overlaps(step: str, previous_steps: list[str]) -> bool:
    """Return whether a requested SfM step overlaps previous requested steps."""
    if step == "sfm":
        return any(previous == "sfm" or previous.startswith("sfm.") for previous in previous_steps)
    return step in previous_steps or "sfm" in previous_steps


def _sqlite_count(database: Path, table: str) -> int:
    """Return a table row count, or zero when the database is unavailable."""
    if not database.exists():
        return 0
    try:
        with sqlite3.connect(database) as connection:
            cursor = connection.execute(f"SELECT COUNT(*) FROM {table}")
            value = cursor.fetchone()
    except sqlite3.Error:
        return 0
    return int(value[0]) if value else 0


def _image_count(path: Path) -> int:
    """Count image files recursively."""
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES)


def inspect_sfm_outputs(run_dir: Path) -> dict[str, dict[str, object]]:
    """Infer SfM stage state from filesystem outputs.

    This is intentionally conservative: it is used to recover interrupted runs
    whose canonical run records are missing or stale.
    """
    sfm_root = run_dir / "sfm"
    database = sfm_root / "database.db"
    selected_sparse = sfm_root / "selected_sparse"
    selected_sparse_text = sfm_root / "selected_sparse_txt"
    undistorted = sfm_root / "undistorted"
    states: dict[str, dict[str, object]] = {}

    image_rows = _sqlite_count(database, "images")
    keypoint_rows = _sqlite_count(database, "keypoints")
    two_view_rows = _sqlite_count(database, "two_view_geometries")
    if image_rows > 0 and keypoint_rows > 0:
        states["sfm.feature_extraction"] = {
            "state": "complete",
            "images": image_rows,
            "keypoint_rows": keypoint_rows,
        }
    elif database.exists():
        states["sfm.feature_extraction"] = {"state": "partial", "database_path": str(database)}
    if two_view_rows > 0:
        states["sfm.matching"] = {"state": "complete", "two_view_geometries": two_view_rows}

    sparse_summary = None
    try:
        sparse_summary = select_sparse_model(list_sparse_models(selected_sparse_text or selected_sparse))
    except ValueError:
        try:
            sparse_summary = select_sparse_model(list_sparse_models(selected_sparse))
        except ValueError:
            sparse_summary = None
    if sparse_summary:
        states["sfm.reconstruction"] = {
            "state": "complete",
            "registered_images": sparse_summary.registered_images,
            "points3d": sparse_summary.points3d,
            "selected_sparse": str(selected_sparse),
        }

    undistorted_images = _image_count(undistorted / "images")
    undistorted_sparse = (undistorted / "sparse").exists()
    undistorted_sparse_summary = None
    if undistorted_sparse:
        try:
            undistorted_sparse_summary = select_sparse_model(list_sparse_models(undistorted / "sparse"))
        except ValueError:
            undistorted_sparse_summary = None
    undistorted_sparse_images = undistorted_sparse_summary.registered_images if undistorted_sparse_summary else 0
    # Binary sparse summaries are intentionally conservative elsewhere and may
    # only report file presence as 1. For undistortion recovery, the image folder
    # itself is the stronger completeness signal when the sparse count is not exact.
    if (
        undistorted_sparse_summary
        and undistorted_sparse_images <= 1
        and undistorted_images > 1
        and not (undistorted / "sparse" / "images.txt").exists()
    ):
        undistorted_sparse_images = undistorted_images
    expected_images = int(
        undistorted_sparse_images
        or (states.get("sfm.reconstruction") or {}).get("registered_images")
        or 0
    )
    if undistorted_images > 0 or undistorted_sparse:
        state = "complete" if expected_images and undistorted_images >= expected_images and undistorted_sparse else "partial"
        states["sfm.undistort"] = {
            "state": state,
            "undistorted_images": undistorted_images,
            "expected_images": expected_images or None,
            "undistorted_sparse_images": undistorted_sparse_images or None,
            "undistorted_sparse_exists": undistorted_sparse,
        }
    return states
