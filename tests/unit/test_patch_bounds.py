"""Tests for patch bounds generation."""

from __future__ import annotations

from reefs.patches.artefacts import SparseImage
from reefs.patches.bounds import generate_patch_bounds


def _image(index: int, x: float) -> SparseImage:
    return SparseImage(
        image_id=index,
        camera_id=1,
        name=f"image_{index:04d}.jpg",
        qvec=(1, 0, 0, 0),
        tvec=(-x, 0, 0),
        center=(x, 0, 0),
        header_line=f"{index} 1 0 0 0 {-x} 0 0 1 image_{index:04d}.jpg",
        points_line="",
    )


def test_generate_patch_bounds_respects_max_cameras() -> None:
    bounds = generate_patch_bounds([_image(index, float(index)) for index in range(5)], max_cameras=2, buffer=0.1)

    assert [item.patch_id for item in bounds] == ["p000", "p001", "p002"]
    assert bounds[0].min_x <= 0
    assert bounds[0].max_x >= 1


def test_generate_patch_bounds_requires_images() -> None:
    try:
        generate_patch_bounds([], max_cameras=2, buffer=0.1)
    except ValueError as exc:
        assert "without registered images" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")
