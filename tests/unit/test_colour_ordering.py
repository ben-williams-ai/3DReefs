"""Tests for shared image ordering."""

from __future__ import annotations

from pathlib import Path

from PIL import ExifTags, Image

from reefs.colour.ordering import build_image_sequence, natural_key


def _write_jpeg_with_timestamp(path: Path, timestamp: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (4, 4), color=(255, 0, 0))
    exif = Image.Exif()
    tag = {name: tag for tag, name in ExifTags.TAGS.items()}["DateTimeOriginal"]
    exif[tag] = timestamp
    image.save(path, exif=exif)


def test_natural_key_orders_numbered_filenames() -> None:
    names = [Path("img10.jpg"), Path("img1.jpg"), Path("img2.jpg")]

    assert sorted(names, key=natural_key) == [
        Path("img1.jpg"),
        Path("img2.jpg"),
        Path("img10.jpg"),
    ]


def test_build_single_camera_sequence_uses_natural_order(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    raw.mkdir()
    for name in ("img10.jpg", "img1.jpg", "img2.jpg"):
        (raw / name).write_text("", encoding="utf-8")

    sequence = build_image_sequence(raw)

    assert sequence.ordering_method == "natural_path"
    assert sequence.relative_paths == [
        Path("img1.jpg"),
        Path("img2.jpg"),
        Path("img10.jpg"),
    ]


def test_build_sequence_prefers_reliable_capture_metadata(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    raw.mkdir()
    _write_jpeg_with_timestamp(raw / "img10.jpg", "2026:01:01 00:00:03")
    _write_jpeg_with_timestamp(raw / "img1.jpg", "2026:01:01 00:00:02")
    _write_jpeg_with_timestamp(raw / "img2.jpg", "2026:01:01 00:00:01")

    sequence = build_image_sequence(raw)

    assert sequence.ordering_method == "capture_metadata"
    assert sequence.relative_paths == [
        Path("img2.jpg"),
        Path("img1.jpg"),
        Path("img10.jpg"),
    ]


def test_build_multi_camera_sequence_preserves_camera_groups(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    (raw / "cam2").mkdir(parents=True)
    (raw / "cam10").mkdir()
    (raw / "cam2" / "img2.jpg").write_text("", encoding="utf-8")
    (raw / "cam10" / "img1.jpg").write_text("", encoding="utf-8")

    sequence = build_image_sequence(raw)

    assert sequence.relative_paths == [
        Path("cam2/img2.jpg"),
        Path("cam10/img1.jpg"),
    ]
    assert [group.name for group in sequence.camera_groups] == ["cam2", "cam10"]
