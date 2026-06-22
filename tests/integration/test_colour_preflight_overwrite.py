"""Tests for corrected-output preflight decisions."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from reefs.colour.pipeline import ExistingOutputDecision, require_preflight_output_decision


def _write_rgb(path: Path, *, size: tuple[int, int] = (4, 4)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size).save(path)


def test_existing_recoloured_outputs_require_explicit_decision(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    recoloured = tmp_path / "recoloured_images"
    raw.mkdir()
    recoloured.mkdir()
    _write_rgb(raw / "img1.jpg")
    _write_rgb(recoloured / "img1.jpg")

    with pytest.raises(ValueError, match="choose resume, overwrite, skip, or fail"):
        require_preflight_output_decision(
            raw_images=raw,
            recoloured_images=recoloured,
            decision=None,
        )


def test_existing_recoloured_outputs_accept_explicit_overwrite(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    recoloured = tmp_path / "recoloured_images"
    raw.mkdir()
    recoloured.mkdir()
    _write_rgb(raw / "img1.jpg")
    _write_rgb(recoloured / "img1.jpg")

    status = require_preflight_output_decision(
        raw_images=raw,
        recoloured_images=recoloured,
        decision=ExistingOutputDecision.OVERWRITE,
    )

    assert status.complete is True


def test_recoloured_outputs_report_dimension_mismatch(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    recoloured = tmp_path / "recoloured_images"
    _write_rgb(raw / "img1.jpg", size=(4, 4))
    _write_rgb(recoloured / "img1.jpg", size=(8, 4))

    status = require_preflight_output_decision(
        raw_images=raw,
        recoloured_images=recoloured,
        decision=ExistingOutputDecision.RESUME,
    )

    assert status.complete is False
    assert status.dimension_mismatches
