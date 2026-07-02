"""Tests for cross-camera pair generation."""

from __future__ import annotations

from pathlib import Path

from reefs.preflight.images import ImageLayout
from reefs.sfm.cross_camera_pairs import generate_cross_camera_pairs


def _layout(names: list[str]) -> ImageLayout:
    return ImageLayout(kind="multi", image_paths=[Path(name) for name in names], camera_dirs=[])


def test_two_camera_numeric_pairs_include_same_and_near_indices() -> None:
    result = generate_cross_camera_pairs(
        _layout(["cam1/img_001.jpg", "cam1/img_002.jpg", "cam2/img_001.jpg", "cam2/img_002.jpg"]),
        index_window=1,
    )

    pairs = {(pair.left, pair.right) for pair in result.pairs}

    assert ("cam1/img_001.jpg", "cam2/img_001.jpg") in pairs
    assert ("cam1/img_001.jpg", "cam2/img_002.jpg") in pairs
    assert result.summary["proposed_cross_camera_pairs"] == 4


def test_three_camera_pairs_all_camera_combinations() -> None:
    result = generate_cross_camera_pairs(
        _layout(["cam1/001.jpg", "cam2/001.jpg", "cam3/001.jpg"]),
        index_window=0,
    )

    pairs = {(pair.left, pair.right) for pair in result.pairs}

    assert pairs == {
        ("cam1/001.jpg", "cam2/001.jpg"),
        ("cam1/001.jpg", "cam3/001.jpg"),
        ("cam2/001.jpg", "cam3/001.jpg"),
    }


def test_unequal_counts_warn_and_still_generate_available_pairs() -> None:
    result = generate_cross_camera_pairs(
        _layout(["cam1/001.jpg", "cam1/002.jpg", "cam2/001.jpg"]),
        index_window=0,
    )

    assert len(result.pairs) == 1
    assert "camera folders have unequal image counts" in result.summary["warnings"]


def test_missing_numeric_frames_warn() -> None:
    result = generate_cross_camera_pairs(
        _layout(["cam1/001.jpg", "cam1/003.jpg", "cam2/001.jpg", "cam2/003.jpg"]),
        index_window=0,
    )

    assert any("missing 1 numeric frame" in warning for warning in result.summary["warnings"])


def test_non_numeric_filenames_use_natural_order() -> None:
    result = generate_cross_camera_pairs(
        _layout(["cam1/a.jpg", "cam1/b.jpg", "cam2/x.jpg", "cam2/y.jpg"]),
        index_window=0,
    )

    assert [(pair.left, pair.right) for pair in result.pairs] == [
        ("cam1/a.jpg", "cam2/x.jpg"),
        ("cam1/b.jpg", "cam2/y.jpg"),
    ]
    assert result.summary["filename_index_parsing_strategy"] == {
        "cam1": "natural_order",
        "cam2": "natural_order",
    }


def test_generation_preserves_layout_order_without_resorting() -> None:
    result = generate_cross_camera_pairs(
        _layout(["cam1/b.jpg", "cam1/a.jpg", "cam2/y.jpg", "cam2/x.jpg"]),
        index_window=0,
    )

    assert [(pair.left, pair.right) for pair in result.pairs] == [
        ("cam1/b.jpg", "cam2/y.jpg"),
        ("cam1/a.jpg", "cam2/x.jpg"),
    ]
    assert result.summary["ordering"] == "exif_timestamp"
    assert result.summary["ordered_cameras"]["cam1"]["first_image"] == "cam1/b.jpg"


def test_filename_ordering_natural_sorts_within_each_camera() -> None:
    result = generate_cross_camera_pairs(
        _layout(["cam1/img10.jpg", "cam1/img2.jpg", "cam2/img10.jpg", "cam2/img2.jpg"]),
        index_window=0,
        ordering="filename",
    )

    assert [(pair.left, pair.right) for pair in result.pairs] == [
        ("cam1/img2.jpg", "cam2/img2.jpg"),
        ("cam1/img10.jpg", "cam2/img10.jpg"),
    ]
    assert result.summary["ordering"] == "filename"
    assert result.summary["ordered_cameras"]["cam1"]["first_image"] == "cam1/img2.jpg"


def test_exif_ordering_warns_when_it_differs_from_filename_order() -> None:
    result = generate_cross_camera_pairs(
        _layout(["cam1/b.jpg", "cam1/a.jpg", "cam2/y.jpg", "cam2/x.jpg"]),
        index_window=0,
    )

    assert "cam1: timestamp ordering differs from natural filename order" in result.summary["warnings"]


def test_numeric_ranges_do_not_override_layout_order() -> None:
    result = generate_cross_camera_pairs(
        _layout(["cam1/DSC00001.jpg", "cam1/DSC00002.jpg", "cam2/DSC06955.jpg", "cam2/DSC06956.jpg"]),
        index_window=0,
    )

    assert [(pair.left, pair.right) for pair in result.pairs] == [
        ("cam1/DSC00001.jpg", "cam2/DSC06955.jpg"),
        ("cam1/DSC00002.jpg", "cam2/DSC06956.jpg"),
    ]
    assert result.summary["filename_index_parsing_strategy"] == {
        "cam1": "numeric_filename",
        "cam2": "numeric_filename",
    }


def test_single_camera_noops_cleanly() -> None:
    result = generate_cross_camera_pairs(
        ImageLayout(kind="single", image_paths=[Path("001.jpg")], camera_dirs=[]),
        index_window=1,
    )

    assert result.pairs == []
    assert result.summary["proposed_cross_camera_pairs"] == 0
