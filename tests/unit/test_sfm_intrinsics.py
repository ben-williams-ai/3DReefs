"""Tests for SfM intrinsics selection."""

from __future__ import annotations

from pathlib import Path

from reefs.diagnostics.images import CameraDimensionReport
from reefs.preflight.images import ImageLayout
from reefs.sfm.intrinsics import (
    camera_intrinsics_by_group_from_sparse_text,
    camera_params_from_cameras_txt,
    choose_intrinsics,
    select_calibration_images,
)


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


def test_camera_params_from_cameras_txt_rejects_multiple_cameras(tmp_path: Path) -> None:
    cameras = tmp_path / "cameras.txt"
    cameras.write_text(
        "\n".join(
            [
                "1 OPENCV 64 48 1 2 3 4 0.1 0.2 0.3 0.4",
                "2 OPENCV 64 48 5 6 7 8 0.5 0.6 0.7 0.8",
            ]
        ),
        encoding="utf-8",
    )

    try:
        camera_params_from_cameras_txt(cameras)
    except ValueError as exc:
        assert "only safe for one camera" in str(exc)
    else:
        raise AssertionError("Expected multi-camera params to be rejected")


def test_camera_intrinsics_by_group_from_sparse_text_supports_many_cameras(tmp_path: Path) -> None:
    cameras = tmp_path / "cameras.txt"
    images = tmp_path / "images.txt"
    cameras.write_text(
        "\n".join(
            [
                "1 OPENCV 64 48 1 2 3 4 0.1 0.2 0.3 0.4",
                "2 OPENCV 64 48 5 6 7 8 0.5 0.6 0.7 0.8",
                "3 OPENCV 64 48 9 10 11 12 0.9 1.0 1.1 1.2",
            ]
        ),
        encoding="utf-8",
    )
    images.write_text(
        "\n".join(
            [
                "1 1 0 0 0 0 0 0 1 cam1/a.jpg",
                "",
                "2 1 0 0 0 0 0 0 2 cam2/a.jpg",
                "",
                "3 1 0 0 0 0 0 0 3 cam3/a.jpg",
                "",
            ]
        ),
        encoding="utf-8",
    )

    intrinsics = camera_intrinsics_by_group_from_sparse_text(
        cameras_txt=cameras,
        images_txt=images,
    )

    assert set(intrinsics) == {"cam1", "cam2", "cam3"}
    assert intrinsics["cam1"].params == (1.0, 2.0, 3.0, 4.0, 0.1, 0.2, 0.3, 0.4)
    assert intrinsics["cam2"].params == (5.0, 6.0, 7.0, 8.0, 0.5, 0.6, 0.7, 0.8)
    assert intrinsics["cam3"].params == (9.0, 10.0, 11.0, 12.0, 0.9, 1.0, 1.1, 1.2)


def test_camera_intrinsics_by_group_ignores_points2d_rows(tmp_path: Path) -> None:
    cameras = tmp_path / "cameras.txt"
    images = tmp_path / "images.txt"
    cameras.write_text(
        "\n".join(
            [
                "1 OPENCV 64 48 1 2 3 4 0.1 0.2 0.3 0.4",
                "2 OPENCV 64 48 5 6 7 8 0.5 0.6 0.7 0.8",
            ]
        ),
        encoding="utf-8",
    )
    images.write_text(
        "\n".join(
            [
                "1 1 0 0 0 0 0 0 1 cam1/a.jpg",
                "10.0 20.0 -1 30.0 40.0 122430 50.0 60.0 -1 70.0 80.0 99",
                "2 1 0 0 0 0 0 0 2 cam2/a.jpg",
                "11.0 21.0 -1 31.0 41.0 122431 51.0 61.0 -1 71.0 81.0 100",
            ]
        ),
        encoding="utf-8",
    )

    intrinsics = camera_intrinsics_by_group_from_sparse_text(
        cameras_txt=cameras,
        images_txt=images,
    )

    assert set(intrinsics) == {"cam1", "cam2"}
    assert intrinsics["cam1"].camera_id == 1
    assert intrinsics["cam2"].camera_id == 2


def test_camera_intrinsics_by_group_handles_raw_images_symlink_paths(tmp_path: Path) -> None:
    cameras = tmp_path / "cameras.txt"
    images = tmp_path / "images.txt"
    cameras.write_text(
        "\n".join(
            [
                "1 OPENCV 64 48 1 2 3 4 0.1 0.2 0.3 0.4",
                "2 OPENCV 64 48 5 6 7 8 0.5 0.6 0.7 0.8",
            ]
        ),
        encoding="utf-8",
    )
    images.write_text(
        "\n".join(
            [
                "1 1 0 0 0 0 0 0 1 ../../input/dataset/raw_images/cam1/a.jpg",
                "",
                "2 1 0 0 0 0 0 0 2 ../../input/dataset/raw_images/cam2/a.jpg",
                "",
            ]
        ),
        encoding="utf-8",
    )

    intrinsics = camera_intrinsics_by_group_from_sparse_text(
        cameras_txt=cameras,
        images_txt=images,
    )

    assert set(intrinsics) == {"cam1", "cam2"}
    assert intrinsics["cam1"].camera_id == 1
    assert intrinsics["cam2"].camera_id == 2


def test_camera_intrinsics_by_group_rejects_duplicate_camera_ids_for_group(tmp_path: Path) -> None:
    cameras = tmp_path / "cameras.txt"
    images = tmp_path / "images.txt"
    cameras.write_text(
        "\n".join(
            [
                "1 OPENCV 64 48 1 2 3 4 0.1 0.2 0.3 0.4",
                "2 OPENCV 64 48 5 6 7 8 0.5 0.6 0.7 0.8",
            ]
        ),
        encoding="utf-8",
    )
    images.write_text(
        "\n".join(
            [
                "1 1 0 0 0 0 0 0 1 cam1/a.jpg",
                "",
                "2 1 0 0 0 0 0 0 2 cam1/b.jpg",
                "",
            ]
        ),
        encoding="utf-8",
    )

    try:
        camera_intrinsics_by_group_from_sparse_text(cameras_txt=cameras, images_txt=images)
    except ValueError as exc:
        assert "maps to multiple COLMAP camera IDs" in str(exc)
    else:
        raise AssertionError("Expected duplicate camera IDs for one group to be rejected")


def test_choose_intrinsics_maps_user_cameras_file_for_multicamera_layout(tmp_path: Path) -> None:
    cameras = tmp_path / "cameras.txt"
    cameras.write_text(
        "\n".join(
            [
                "2 OPENCV 64 48 5 6 7 8 0.5 0.6 0.7 0.8",
                "1 OPENCV 64 48 1 2 3 4 0.1 0.2 0.3 0.4",
            ]
        ),
        encoding="utf-8",
    )
    layout = ImageLayout(
        kind="multi",
        image_paths=[Path("cam1/a.jpg"), Path("cam2/a.jpg")],
        camera_dirs=["cam1", "cam2"],
    )

    selection = choose_intrinsics(
        layout=layout,
        dimension_reports=[
            CameraDimensionReport("cam1", {(64, 48): [Path("cam1/a.jpg")]}),
            CameraDimensionReport("cam2", {(64, 48): [Path("cam2/a.jpg")]}),
        ],
        camera_model="OPENCV",
        precalculate=True,
        cameras_txt=cameras,
        selection_start_index=50,
        selection_end_index=150,
    )

    assert selection.camera_params is None
    assert selection.camera_intrinsics_by_group is not None
    assert selection.camera_intrinsics_by_group["cam1"].params == (1, 2, 3, 4, 0.1, 0.2, 0.3, 0.4)
    assert selection.camera_intrinsics_by_group["cam2"].params == (5, 6, 7, 8, 0.5, 0.6, 0.7, 0.8)
