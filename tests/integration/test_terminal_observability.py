"""Integration tests for live terminal output."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from reefs.colmap.commands import ColmapCommand
from reefs.colmap.runner import run_colmap_command
from tests.conftest import write_config, write_test_jpeg, write_undistorted_sfm_fixture


def _fake_output_tool(path: Path) -> Path:
    path.write_text("#!/usr/bin/env bash\necho 'tool progress line'\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_colmap_runner_tees_output_to_terminal_and_log(tmp_path: Path, capsys) -> None:
    tool = _fake_output_tool(tmp_path / "fake-colmap")
    log_path = tmp_path / "colmap.log"

    run_colmap_command(ColmapCommand(stage="sfm.extract", args=[str(tool)]), log_path=log_path)

    assert "tool progress line" in capsys.readouterr().out
    assert "tool progress line" in log_path.read_text(encoding="utf-8")


def test_splat_patch_cli_prints_progress_before_lfs(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
    )
    run_dir = project / "runs" / "old"
    run_dir.mkdir(parents=True)
    write_undistorted_sfm_fixture(run_dir)

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "old", "--steps", "splat.patch", "--resume-policy", "overwrite"],
    )

    assert result.exit_code == 0, result.output
    assert "[splat.preflight] started" in result.output
    assert "[splat.outlier_filter] started" in result.output
    assert "Preparing patch source" in result.output
    assert "Generating patch datasets" in result.output
    assert "[splat.patch.p000] selecting cameras" in result.output
    assert "[splat.patch.p000] exporting patch dataset" in result.output
    assert "[splat.patch] complete" in result.output
