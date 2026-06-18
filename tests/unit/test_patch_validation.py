"""Tests for patch metadata validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from reefs.io.yaml_json import write_json
from reefs.patches.selection import SELECTOR_NAME, SELECTOR_VERSION
from reefs.patches.validation import validate_patch_metadata


def _write_required_patch_files(patch_dir: Path) -> None:
    selected_dir = patch_dir / "selected_images"
    selected_dir.mkdir(parents=True)
    (selected_dir / "image_0001.jpg").write_text("image\n", encoding="utf-8")
    sparse_dir = patch_dir / "sparse" / "0"
    sparse_dir.mkdir(parents=True)
    for name in ["cameras.txt", "images.txt", "points3D.txt"]:
        (sparse_dir / name).write_text("data\n", encoding="utf-8")
    diagnostics = patch_dir / "patch_diagnostics"
    diagnostics.mkdir(parents=True)
    (diagnostics / "camera_coverage.csv").write_text("image_name\n", encoding="utf-8")
    (diagnostics / "generation.log").write_text("ok\n", encoding="utf-8")


def test_validate_patch_metadata_requires_nested_bounds(tmp_path: Path) -> None:
    patch_dir = tmp_path / "p000"
    patch_dir.mkdir()
    _write_required_patch_files(patch_dir)
    write_json(
        patch_dir / "patch_metadata.json",
        {
            "patch_id": "p000",
            "min_x": 0,
            "max_x": 1,
            "min_y": 0,
            "max_y": 1,
            "min_z": 0,
            "max_z": 1,
            "selected_images": ["image_0001.jpg"],
            "selected_camera_count": 1,
            "selector": {
                "name": SELECTOR_NAME,
                "version": SELECTOR_VERSION,
                "signature": {},
                "coverage": {},
                "warning_thresholds": {},
            },
            "sparse_point_count": 1,
        },
    )

    with pytest.raises(ValueError, match="canonical nested bounds"):
        validate_patch_metadata(patch_dir, max_cameras=10)


def test_validate_patch_metadata_accepts_canonical_nested_bounds(tmp_path: Path) -> None:
    patch_dir = tmp_path / "p000"
    patch_dir.mkdir()
    _write_required_patch_files(patch_dir)
    write_json(
        patch_dir / "patch_metadata.json",
        {
            "patch_id": "p000",
            "bounds": {
                "min_x": 0,
                "max_x": 1,
                "min_y": 0,
                "max_y": 1,
                "min_z": 0,
                "max_z": 1,
                "buffer": 0.1,
            },
            "selected_images": ["image_0001.jpg"],
            "selected_camera_count": 1,
            "selector": {
                "name": SELECTOR_NAME,
                "version": SELECTOR_VERSION,
                "signature": {},
                "coverage": {},
                "warning_thresholds": {},
            },
            "sparse_point_count": 1,
        },
    )

    metadata = validate_patch_metadata(patch_dir, max_cameras=10)

    assert metadata["status"] == "valid"
