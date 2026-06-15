"""Tests for camera pose outlier filtering."""

from __future__ import annotations

from reefs.patches.artefacts import SparseImage, SparseScene
from reefs.patches.outliers import detect_camera_pose_outliers


def _image(image_id: int, x: float) -> SparseImage:
    return SparseImage(
        image_id=image_id,
        camera_id=1,
        name=f"image_{image_id}.jpg",
        qvec=(1, 0, 0, 0),
        tvec=(-x, 0, 0),
        center=(x, 0, 0),
        header_line=f"{image_id} 1 0 0 0 {-x} 0 0 1 image_{image_id}.jpg",
        points_line="",
    )


def test_detect_camera_pose_outliers_removes_small_clear_tail(tmp_path) -> None:
    scene = SparseScene(
        model_dir=tmp_path,
        cameras_text="",
        images=[*[_image(index, float(index)) for index in range(10)], _image(99, 1000.0)],
        points=[],
    )

    result = detect_camera_pose_outliers(
        scene,
        method="iqr",
        iqr_mult=1.5,
        percentile=99.9,
        max_removal_fraction=0.2,
        dry_run=False,
    )

    assert result.state == "complete_removed_outliers"
    assert result.removed_image_ids == {99}


def test_detect_camera_pose_outliers_blocks_ambiguous_large_removal(tmp_path) -> None:
    scene = SparseScene(
        model_dir=tmp_path,
        cameras_text="",
        images=[*[_image(index, float(index)) for index in range(10)], _image(99, 1000.0), _image(100, 1100.0)],
        points=[],
    )

    result = detect_camera_pose_outliers(
        scene,
        method="iqr",
        iqr_mult=1.0,
        percentile=99.9,
        max_removal_fraction=0.05,
        dry_run=False,
    )

    assert result.state == "blocked_ambiguous"
    assert result.removed_image_ids == set()
    assert result.warnings


def test_detect_camera_pose_outliers_dry_run_only_proposes(tmp_path) -> None:
    scene = SparseScene(
        model_dir=tmp_path,
        cameras_text="",
        images=[*[_image(index, float(index)) for index in range(10)], _image(99, 1000.0)],
        points=[],
    )

    result = detect_camera_pose_outliers(
        scene,
        method="iqr",
        iqr_mult=1.5,
        percentile=99.9,
        max_removal_fraction=0.2,
        dry_run=True,
    )

    assert result.state == "dry_run_reported"
    assert result.removed_image_ids == set()
    assert {record.decision for record in result.records} >= {"kept", "proposed"}
