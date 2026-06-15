"""Tests for outlier diagnostic plot export."""

from __future__ import annotations

from pathlib import Path

from reefs.diagnostics.patch_plots import write_outlier_pose_diagnostics
from reefs.patches.outliers import CameraOutlierRecord, OutlierFilterResult


def test_write_outlier_pose_diagnostics_creates_four_views(tmp_path: Path) -> None:
    result = OutlierFilterResult(
        records=[
            CameraOutlierRecord(1, "a.jpg", (0, 0, 0), "iqr", {}, 0.0, 0.0, "kept", "inside"),
            CameraOutlierRecord(2, "b.jpg", (10, 0, 1), "iqr", {}, 10.0, 0.0, "removed", "outside"),
        ],
        removed_image_ids={2},
        kept_image_ids={1},
        state="complete_removed_outliers",
        warnings=[],
    )

    warnings = write_outlier_pose_diagnostics(result, tmp_path)

    assert warnings == []
    for name in [
        "camera_pose_top_before.png",
        "camera_pose_top_after.png",
        "camera_pose_side_before.png",
        "camera_pose_side_after.png",
    ]:
        assert (tmp_path / name).exists()
