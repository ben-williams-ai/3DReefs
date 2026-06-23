"""Tests for patch selection before LFS training."""

from __future__ import annotations

from pathlib import Path

import pytest

from reefs.config.models import PipelineConfig
from reefs.io.yaml_json import write_json
from reefs.patches.selection import SELECTOR_NAME, SELECTOR_VERSION
from reefs.splat.pipeline import _selected_training_patch_records


def _config(tmp_path: Path, patch_ids: list[str] | None = None):
    return PipelineConfig.model_validate(
        {
            "colour_restoration": {"mode": "off"},
            "project": {"dir": str(tmp_path)},
            "tools": {},
            "advanced": {"splat": {"train": {"patch_ids": patch_ids}}},
        }
    )


def _patch(root: Path, patch_id: str) -> None:
    patch_dir = root / patch_id
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
    write_json(
        patch_dir / "patch_metadata.json",
        {
            "patch_id": patch_id,
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
            "sparse_point_count": 1,
            "selector": {
                "name": SELECTOR_NAME,
                "version": SELECTOR_VERSION,
                "signature": {},
                "coverage": {
                    "selected_internal_count": 1,
                    "rejected_internal_count": 0,
                    "selected_external_count": 0,
                    "unused_external_count": 0,
                    "max_cameras": 800,
                    "external_support_fraction": 0.10,
                    "external_support_allowance": 80,
                    "internal_patch_target": 720,
                },
                "warning_thresholds": {},
            },
            "status": "valid",
        },
    )


def test_selected_training_patch_records_uses_explicit_patch_ids(tmp_path: Path) -> None:
    patches = tmp_path / "patches"
    _patch(patches, "p000")
    _patch(patches, "p001")

    records = _selected_training_patch_records(_config(tmp_path, ["p001"]), patches)

    assert [record["patch_id"] for record in records] == ["p001"]


def test_selected_training_patch_records_rejects_unknown_ids(tmp_path: Path) -> None:
    patches = tmp_path / "patches"
    _patch(patches, "p000")

    with pytest.raises(ValueError, match="do not exist"):
        _selected_training_patch_records(_config(tmp_path, ["p999"]), patches)
