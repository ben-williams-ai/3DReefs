"""Tests for multi-camera colour output identity."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from reefs.colour.filters import ColourParameterSet
from reefs.colour.pipeline import apply_corrections


def test_multicamera_apply_preserves_camera_folders(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    recoloured = tmp_path / "recoloured_images"
    for relative in (Path("cam1/img1.jpg"), Path("cam2/img1.jpg")):
        (raw / relative).parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (6, 4), color=(10, 20, 30)).save(raw / relative)

    status = apply_corrections(
        raw_images=raw,
        recoloured_images=recoloured,
        parameters_by_path={
            Path("cam1/img1.jpg"): ColourParameterSet(warmth=0.1),
            Path("cam2/img1.jpg"): ColourParameterSet(tint=0.1),
        },
    )

    assert status.complete is True
    assert (recoloured / "cam1" / "img1.jpg").exists()
    assert (recoloured / "cam2" / "img1.jpg").exists()
