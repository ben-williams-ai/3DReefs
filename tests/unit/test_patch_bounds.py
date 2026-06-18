"""Tests for patch bounds generation."""

from __future__ import annotations

import sys
import types

from reefs.patches.artefacts import SparseImage
from reefs.patches.bounds import generate_patch_bounds, validate_patch_bounds_backend
from reefs.patches.selection import derive_patch_camera_targets


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


def test_generate_patch_bounds_uses_wildflow_patches(monkeypatch) -> None:
    wildflow = types.ModuleType("wildflow")
    splat = types.ModuleType("wildflow.splat")
    calls: list[dict[str, object]] = []

    def patches(cameras, *, max_cameras, buffer_meters):
        calls.append({"cameras": cameras, "max_cameras": max_cameras, "buffer_meters": buffer_meters})
        return [{"min_x": -1, "max_x": 2, "min_y": -3, "max_y": 4}]

    splat.patches = patches
    wildflow.splat = splat
    monkeypatch.setitem(sys.modules, "wildflow", wildflow)
    monkeypatch.setitem(sys.modules, "wildflow.splat", splat)

    bounds = generate_patch_bounds([_image(1, 10), _image(2, 20)], max_cameras=800, buffer=0.1)

    assert calls == [{"cameras": [(10.0, 0.0), (20.0, 0.0)], "max_cameras": 800, "buffer_meters": 0.1}]
    assert bounds[0].as_dict() == {
        "min_x": -1.0,
        "max_x": 2.0,
        "min_y": -3.0,
        "max_y": 4.0,
        "min_z": -0.1,
        "max_z": 0.1,
        "buffer": 0.1,
    }


def test_generate_patch_bounds_can_use_internal_patch_target(monkeypatch) -> None:
    wildflow = types.ModuleType("wildflow")
    splat = types.ModuleType("wildflow.splat")
    calls: list[int] = []

    def patches(cameras, *, max_cameras, buffer_meters):
        calls.append(max_cameras)
        return [{"min_x": -1, "max_x": 2, "min_y": -3, "max_y": 4}]

    splat.patches = patches
    wildflow.splat = splat
    monkeypatch.setitem(sys.modules, "wildflow", wildflow)
    monkeypatch.setitem(sys.modules, "wildflow.splat", splat)
    targets = derive_patch_camera_targets(400, 0.10)

    generate_patch_bounds(
        [_image(1, 10), _image(2, 20)],
        max_cameras=int(targets["internal_patch_target"]),
        buffer=0.1,
    )

    assert calls == [360]


def test_validate_patch_bounds_backend_requires_wildflow_patches(monkeypatch) -> None:
    wildflow = types.ModuleType("wildflow")
    splat = types.ModuleType("wildflow.splat")
    wildflow.splat = splat
    monkeypatch.setitem(sys.modules, "wildflow", wildflow)
    monkeypatch.setitem(sys.modules, "wildflow.splat", splat)

    result = validate_patch_bounds_backend()

    assert result.status == "failed"
    assert "patches" in result.message


def test_generate_patch_bounds_requires_images() -> None:
    try:
        generate_patch_bounds([], max_cameras=2, buffer=0.1)
    except ValueError as exc:
        assert "without registered images" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")
