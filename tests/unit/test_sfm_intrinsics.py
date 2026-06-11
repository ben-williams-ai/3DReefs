"""Tests for SfM intrinsics selection."""

from __future__ import annotations

from pathlib import Path

from reefs.preflight.images import ImageLayout
from reefs.sfm.intrinsics import camera_params_from_cameras_txt, select_calibration_images


def test_short_sequence_uses_available_images() -> None:
    layout = ImageLayout(
        kind="single",
        image_paths=[Path("a.jpg"), Path("b.jpg")],
        camera_dirs=[],
    )

    selected, warnings = select_calibration_images(
        layout=layout,
        selection_start_index=50,
        selection_end_index=150,
    )

    assert selected["single"] == ["a.jpg", "b.jpg"]
    assert warnings


def test_camera_params_from_cameras_txt(tmp_path: Path) -> None:
    cameras = tmp_path / "cameras.txt"
    cameras.write_text(
        "# comment\n1 OPENCV 64 48 1 2 3 4 0.1 0.2 0.3 0.4\n",
        encoding="utf-8",
    )

    assert camera_params_from_cameras_txt(cameras) == "1.0,2.0,3.0,4.0,0.1,0.2,0.3,0.4"
