"""Integration tests for CLI override persistence."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from reefs.cli import app
from tests.conftest import write_config


def test_overrides_are_recorded_and_applied(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    (project / "raw_images").mkdir(parents=True)
    (project / "raw_images" / "image_0001.jpg").write_text("", encoding="utf-8")
    colmap = fake_tool_factory("colmap", "COLMAP 4.0.4")
    lfs = fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")
    sog = fake_tool_factory("splat-transform", "splat-transform 1.0")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=tmp_path / "wrong",
        colmap_bin=colmap,
        lfs_bin=lfs,
        splat_transform_bin=sog,
    )

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--project-dir",
            str(project),
            "--steps",
            "sfm,splat",
            "--resume-policy",
            "resume",
            "--splat.train.num_iters",
            "20000",
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = next((project / "runs").iterdir())
    overrides = json.loads((run_dir / "cli_overrides.json").read_text(encoding="utf-8"))
    effective = yaml.safe_load((run_dir / "effective_config.yml").read_text(encoding="utf-8"))
    assert overrides["project_dir_override"] == str(project)
    assert overrides["requested_steps"] == ["sfm", "splat"]
    assert overrides["resume_policy"] == "resume"
    assert overrides["overrides"][0]["parsed_value"] == 20000
    assert effective["splat"]["train"]["num_iters"] == 20000


def test_unknown_override_fails_before_run_output(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    (project / "raw_images").mkdir(parents=True)
    (project / "raw_images" / "image_0001.jpg").write_text("", encoding="utf-8")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
    )

    result = CliRunner().invoke(app, ["--config", str(config), "--missing.value", "1"])

    assert result.exit_code != 0
    assert "Unknown override key" in result.output
    assert not (project / "runs").exists()
