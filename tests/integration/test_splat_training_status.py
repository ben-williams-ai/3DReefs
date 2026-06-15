"""Integration tests for patch-level training status records."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from tests.conftest import write_config, write_test_jpeg, write_undistorted_sfm_fixture
from tests.integration.test_splat_mocked_success import _fake_lfs


def test_mocked_lfs_training_manifest_contains_iteration_status(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=_fake_lfs(tmp_path / "LichtFeld-Studio"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
    )
    run_dir = project / "runs" / "old"
    run_dir.mkdir(parents=True)
    write_undistorted_sfm_fixture(run_dir)
    assert CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "old", "--steps", "splat.patch", "--resume-policy", "overwrite"],
    ).exit_code == 0

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "old",
            "--steps",
            "splat.train",
            "--advanced.splat.train.num_iters",
            "500",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    manifest = json.loads((run_dir / "splat" / "training" / "training_manifest.json").read_text(encoding="utf-8"))
    assert manifest[0]["requested_iterations"] == 500
    assert manifest[0]["completed_iterations"] == 500
