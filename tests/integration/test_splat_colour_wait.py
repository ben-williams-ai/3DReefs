"""Tests for splat waiting on colour restoration state."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from reefs.colour.pipeline import colour_state_path
from reefs.colour.state import ColourRestorationState, ColourStatus, save_state
from tests.conftest import write_config, write_test_jpeg, write_undistorted_sfm_fixture


def test_splat_waits_while_colour_state_is_active(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        recolour_images=True,
    )
    run_dir = project / "runs" / "old"
    run_dir.mkdir(parents=True)
    write_undistorted_sfm_fixture(run_dir)
    save_state(
        colour_state_path(run_dir),
        ColourRestorationState(
            run_id="old",
            source_raw_root=project / "raw_images",
            output_recoloured_root=project / "recoloured_images",
            status=ColourStatus.ACTIVE,
            active_session=True,
        ),
    )

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "old", "--steps", "splat.preflight"],
    )

    assert result.exit_code != 0
    assert "splatting is waiting for colour restoration" in result.output


def test_splat_continues_when_colour_state_is_skipped(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        recolour_images=True,
    )
    run_dir = project / "runs" / "old"
    run_dir.mkdir(parents=True)
    write_undistorted_sfm_fixture(run_dir)
    save_state(
        colour_state_path(run_dir),
        ColourRestorationState(
            run_id="old",
            source_raw_root=project / "raw_images",
            output_recoloured_root=project / "recoloured_images",
            status=ColourStatus.SKIPPED,
        ),
    )

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "old", "--steps", "splat.preflight"],
    )

    assert result.exit_code == 0, result.output
