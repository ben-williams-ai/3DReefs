"""Tests for patch selection before LFS training."""

from __future__ import annotations

from pathlib import Path

import pytest

from reefs.config.models import PipelineConfig
from reefs.io.yaml_json import write_json
from reefs.patches.selection import SELECTOR_NAME, SELECTOR_VERSION, WARNING_THRESHOLDS, selector_signature
from reefs.splat.pipeline import _selected_training_patch_records


def _config(tmp_path: Path, patch_ids: list[str] | None = None):
    return PipelineConfig.model_validate(
        {
            "project": {"dir": str(tmp_path)},
            "tools": {},
            "advanced": {"splat": {"train": {"patch_ids": patch_ids}}},
        }
    )


def _patch(root: Path, patch_id: str) -> None:
    patch_dir = root / patch_id
    patch_dir.mkdir(parents=True)
    patch_affecting_config = {"patching": {"max_cameras": 800}, "selector": {"name": SELECTOR_NAME}}
    write_json(
        patch_dir / "patch_metadata.json",
        {
            "patch_id": patch_id,
            "status": "valid",
            "selected_images": ["image_0001.jpg"],
            "selected_image_count": 1,
            "bounds": {
                "min_x": 0,
                "max_x": 1,
                "min_y": 0,
                "max_y": 1,
                "min_z": 0,
                "max_z": 1,
                "buffer": 0.1,
            },
            "selector": {
                "name": SELECTOR_NAME,
                "version": SELECTOR_VERSION,
                "signature": selector_signature(
                    patch_affecting_config=patch_affecting_config,
                    source_sparse="sparse",
                ),
                "coverage": {"footprint": 1.0, "view_direction_bins": 1.0},
                "warning_thresholds": WARNING_THRESHOLDS,
            },
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
