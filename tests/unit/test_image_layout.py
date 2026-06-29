"""Tests for image layout validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import ExifTags, Image

from reefs.preflight.images import detect_image_layout, validate_recoloured_mirror


def _write_jpeg_with_timestamp(path: Path, timestamp: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (4, 4), color=(255, 0, 0))
    exif = Image.Exif()
    tag = {name: tag for tag, name in ExifTags.TAGS.items()}["DateTimeOriginal"]
    exif[tag] = timestamp
    image.save(path, exif=exif)


def test_detect_single_camera_layout(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    raw.mkdir()
    (raw / "image_0001.jpg").write_text("", encoding="utf-8")

    layout = detect_image_layout(raw)

    assert layout.kind == "single"
    assert layout.relative_image_paths == [Path("image_0001.jpg")]


def test_detect_single_camera_layout_uses_natural_order(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    raw.mkdir()
    for name in ("img10.jpg", "img1.jpg", "img2.jpg"):
        (raw / name).write_text("", encoding="utf-8")

    layout = detect_image_layout(raw)

    assert layout.relative_image_paths == [
        Path("img1.jpg"),
        Path("img2.jpg"),
        Path("img10.jpg"),
    ]


def test_detect_multi_camera_layout(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    (raw / "cam1").mkdir(parents=True)
    (raw / "cam2").mkdir()
    (raw / "cam1" / "image_0001.jpg").write_text("", encoding="utf-8")
    (raw / "cam2" / "image_0001.jpg").write_text("", encoding="utf-8")

    layout = detect_image_layout(raw)

    assert layout.kind == "multi"
    assert layout.relative_image_paths == [
        Path("cam1/image_0001.jpg"),
        Path("cam2/image_0001.jpg"),
    ]


def test_detect_layout_uses_capture_time_with_natural_tie_break(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    _write_jpeg_with_timestamp(raw / "cam1" / "DSC09999.jpg", "2026:01:01 00:00:01")
    _write_jpeg_with_timestamp(raw / "cam1" / "DSC00001.jpg", "2026:01:01 00:00:02")
    _write_jpeg_with_timestamp(raw / "cam1" / "DSC00002.jpg", "2026:01:01 00:00:02")

    layout = detect_image_layout(raw)

    assert layout.relative_image_paths == [
        Path("cam1/DSC09999.jpg"),
        Path("cam1/DSC00001.jpg"),
        Path("cam1/DSC00002.jpg"),
    ]
    assert layout.ordering_reports[0].method == "capture_metadata"
    assert layout.ordering_warnings


def test_detect_multi_camera_layout_does_not_interleave_camera_groups_by_time(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw_images"
    _write_jpeg_with_timestamp(raw / "cam1" / "a.jpg", "2026:01:01 00:00:02")
    _write_jpeg_with_timestamp(raw / "cam2" / "a.jpg", "2026:01:01 00:00:01")

    layout = detect_image_layout(raw)

    assert layout.relative_image_paths == [Path("cam1/a.jpg"), Path("cam2/a.jpg")]


def test_detect_layout_falls_back_to_natural_order_without_exif(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    (raw / "cam1").mkdir(parents=True)
    for name in ["img10.jpg", "img1.jpg", "img2.jpg"]:
        (raw / "cam1" / name).write_text("", encoding="utf-8")

    layout = detect_image_layout(raw)

    assert layout.relative_image_paths == [
        Path("cam1/img1.jpg"),
        Path("cam1/img2.jpg"),
        Path("cam1/img10.jpg"),
    ]
    assert layout.ordering_reports[0].method == "natural_path"
    assert layout.ordering_warnings


def test_reject_mixed_layout(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    (raw / "cam1").mkdir(parents=True)
    (raw / "image_0001.jpg").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="mixes direct images"):
        detect_image_layout(raw)


def test_validate_recoloured_mirror(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    recoloured = tmp_path / "recoloured_images"
    raw.mkdir()
    recoloured.mkdir()
    (raw / "image_0001.jpg").write_text("", encoding="utf-8")
    (recoloured / "image_0001.jpg").write_text("", encoding="utf-8")
    layout = detect_image_layout(raw)

    validate_recoloured_mirror(
        raw_images=raw, recoloured_images=recoloured, layout=layout
    )


def test_recoloured_mirror_reports_missing(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    recoloured = tmp_path / "recoloured_images"
    raw.mkdir()
    recoloured.mkdir()
    (raw / "image_0001.jpg").write_text("", encoding="utf-8")
    layout = detect_image_layout(raw)

    with pytest.raises(ValueError, match="missing recoloured images"):
        validate_recoloured_mirror(
            raw_images=raw, recoloured_images=recoloured, layout=layout
        )
