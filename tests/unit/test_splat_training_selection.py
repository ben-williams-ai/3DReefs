"""Tests for patch selection before LFS training."""

from __future__ import annotations

from pathlib import Path

import pytest

from reefs.config.models import PipelineConfig
from reefs.io.yaml_json import write_json
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
    write_json(patch_dir / "patch_metadata.json", {"patch_id": patch_id, "status": "valid"})


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
