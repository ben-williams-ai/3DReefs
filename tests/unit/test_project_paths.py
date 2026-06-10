"""Tests for project path derivation."""

from __future__ import annotations

from pathlib import Path

from reefs.config.models import PipelineConfig
from reefs.io.paths import derive_project_paths


def test_derive_default_project_paths(tmp_path: Path) -> None:
    config = PipelineConfig.model_validate(
        {"project": {"dir": tmp_path, "recolour_images": False}}
    )

    paths = derive_project_paths(config)

    assert paths.project_dir == tmp_path.resolve()
    assert paths.raw_images == (tmp_path / "raw_images").resolve()
    assert paths.recoloured_images == (tmp_path / "recoloured_images").resolve()
    assert paths.runs == (tmp_path / "runs").resolve()


def test_project_dir_override_changes_derived_paths(tmp_path: Path) -> None:
    source = tmp_path / "source"
    override = tmp_path / "override"
    config = PipelineConfig.model_validate(
        {"project": {"dir": source, "recolour_images": False}}
    )

    paths = derive_project_paths(config, override)

    assert paths.project_dir == override.resolve()
    assert paths.raw_images == (override / "raw_images").resolve()
