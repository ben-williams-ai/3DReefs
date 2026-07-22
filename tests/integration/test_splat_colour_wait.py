"""Tests for splat waiting on colour restoration state."""

from __future__ import annotations

import json
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
        colour_restoration_mode="manual",
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
        colour_restoration_mode="manual",
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


def test_splat_preflight_ignores_active_colour_state_when_mode_is_off(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        colour_restoration_mode="off",
    )
    run_dir = project / "runs" / "off"
    run_dir.mkdir(parents=True)
    write_undistorted_sfm_fixture(run_dir)
    save_state(
        colour_state_path(run_dir),
        ColourRestorationState(
            run_id="off",
            source_raw_root=project / "raw_images",
            output_recoloured_root=project / "recoloured_images",
            restoration_mode="manual",
            status=ColourStatus.ACTIVE,
            active_session=True,
        ),
    )

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "off", "--steps", "splat.preflight"],
    )

    assert result.exit_code == 0, result.output


def test_gray_world_selects_corrected_undistorted_splat_images(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    raw = project / "raw_images"
    recoloured = project / "recoloured_images"
    write_test_jpeg(raw / "image_0001.jpg")
    write_test_jpeg(recoloured / "image_0001.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        colour_restoration_mode="gray_world",
    )
    run_dir = project / "runs" / "gray"
    run_dir.mkdir(parents=True)
    write_undistorted_sfm_fixture(run_dir)
    from PIL import Image

    Image.new("RGB", (64, 48), (10, 20, 30)).save(
        run_dir / "sfm" / "undistorted" / "images" / "image_0001.jpg"
    )
    save_state(
        colour_state_path(run_dir),
        ColourRestorationState(
            run_id="gray",
            source_raw_root=raw,
            output_recoloured_root=recoloured,
            restoration_mode="gray_world",
            status=ColourStatus.COMPLETE,
            splat_image_source="recoloured",
            splat_images_path=recoloured,
        ),
    )

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "gray", "--steps", "splat.preflight"],
    )

    assert result.exit_code == 0, result.output
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["splat_preflight"]["source"]["paths"]["image_source"] == "corrected_undistorted"
    assert manifest["splat_preflight"]["source"]["paths"]["images_dir"] == str(
        run_dir / "colour_restoration" / "outputs" / "undistorted" / "images"
    )
