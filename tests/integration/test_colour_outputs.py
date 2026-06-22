"""Tests for corrected image output generation."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from reefs.colour.filters import ColourParameterSet
from reefs.colour.pipeline import apply_corrections, correct_image_file


def test_apply_corrections_preserves_paths_dimensions_extension_and_rgb(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    recoloured = tmp_path / "recoloured_images"
    source = raw / "cam1" / "img1.jpg"
    source.parent.mkdir(parents=True)
    Image.new("RGB", (12, 8), color=(10, 20, 30)).save(source)

    status = apply_corrections(
        raw_images=raw,
        recoloured_images=recoloured,
        parameters_by_path={Path("cam1/img1.jpg"): ColourParameterSet(brightness=0.1)},
    )

    output = recoloured / "cam1" / "img1.jpg"
    assert status.complete is True
    assert output.exists()
    with Image.open(output) as image:
        assert image.mode == "RGB"
        assert image.size == (12, 8)


def test_jpeg_outputs_use_high_quality_save_settings(tmp_path: Path, monkeypatch) -> None:
    raw = tmp_path / "raw_images" / "img1.jpg"
    raw.parent.mkdir(parents=True)
    Image.new("RGB", (12, 8), color=(10, 20, 30)).save(raw)
    captured: dict[str, object] = {}
    original_save = Image.Image.save

    def capture_save(self, fp, format=None, **params):  # noqa: ANN001, ANN202 - mirrors Pillow signature.
        captured.update(params)
        return original_save(self, fp, format=format, **params)

    monkeypatch.setattr(Image.Image, "save", capture_save)

    correct_image_file(
        source=raw,
        destination=tmp_path / "recoloured_images" / "img1.jpg",
        parameters=ColourParameterSet(),
    )

    assert captured["quality"] == 95
    assert captured["subsampling"] == 0
