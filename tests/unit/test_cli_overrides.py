"""Tests for CLI override handling."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from reefs.cli import app
from reefs.config.models import PipelineConfig
from reefs.config.overrides import apply_overrides, parse_unknown_overrides


def test_parse_dotted_override() -> None:
    overrides = parse_unknown_overrides(["--advanced.splat.train.num_iters", "20000"])

    assert overrides[0]["key"] == "advanced.splat.train.num_iters"
    assert overrides[0]["raw_value"] == "20000"


def test_apply_override_with_type_coercion(tmp_path: Path) -> None:
    config = PipelineConfig.model_validate(
        {
            "project": {"dir": tmp_path, "recolour_images": False},
            "tools": {
                "colmap_bin": "colmap",
                "lfs_bin": "LichtFeld-Studio",
                "splat_transform_bin": "splat-transform",
            },
        }
    )

    updated, records = apply_overrides(
        config,
        parse_unknown_overrides(["--advanced.splat.train.num_iters", "20000"]),
    )

    assert updated.advanced.splat.train.num_iters == 20000
    assert records[0]["parsed_value"] == 20000


def test_unknown_override_fails(tmp_path: Path) -> None:
    config = PipelineConfig.model_validate(
        {
            "project": {"dir": tmp_path, "recolour_images": False},
            "tools": {
                "colmap_bin": "colmap",
                "lfs_bin": "LichtFeld-Studio",
                "splat_transform_bin": "splat-transform",
            },
        }
    )

    with pytest.raises(ValueError, match="Unknown override key"):
        apply_overrides(config, parse_unknown_overrides(["--missing.value", "1"]))


def test_cli_accepts_project_dir_steps_and_resume_policy(tmp_path: Path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
project:
  dir: /tmp/example
  recolour_images: false
tools:
  colmap_bin: colmap
  lfs_bin: LichtFeld-Studio
  splat_transform_bin: splat-transform
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "--project-dir",
            str(tmp_path),
            "--steps",
            "sfm,splat",
            "--resume-policy",
            "fail",
        ],
    )

    assert "raw_images directory does not exist" in result.output
