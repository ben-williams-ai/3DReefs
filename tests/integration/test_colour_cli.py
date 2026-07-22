"""Tests for standalone colour CLI commands."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from click.testing import CliRunner
from PIL import Image

from reefs.cli import app
from reefs.colour.filters import ColourParameterSet
from reefs.colour.gui import ColourGuiController
from reefs.colour.interpolation import rebuild_keyframes
from reefs.colour.ordering import build_image_sequence
from reefs.colour.pipeline import colour_state_path, initialise_state
from reefs.colour.state import ColourStatus, load_state, save_state
from tests.conftest import write_config


def test_colour_apply_uses_completed_undistorted_workspace(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    raw = project / "raw_images"
    raw.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(raw / "img1.jpg")
    run_dir = project / "runs" / "colour-run"
    run_dir.mkdir(parents=True)
    undistorted = run_dir / "sfm" / "undistorted" / "images"
    undistorted.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(undistorted / "img1.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        colour_restoration_mode="manual",
    )
    state = initialise_state(
        run_id="colour-run",
        run_dir=run_dir,
        raw_images=raw,
        recoloured_images=project / "recoloured_images",
    )
    keyframe = replace(
        rebuild_keyframes(build_image_sequence(raw), count=1)[0],
        edited=True,
        parameters=ColourParameterSet(brightness=0.1),
    )
    save_state(colour_state_path(run_dir), replace(state, keyframes=[keyframe]))

    result = CliRunner().invoke(
        app,
        ["colour", "apply", "--config", str(config), "--run-id", "colour-run"],
    )

    assert result.exit_code == 0, result.output
    assert "complete" in result.output
    assert (
        run_dir / "colour_restoration" / "outputs" / "undistorted" / "images" / "img1.jpg"
    ).exists()
    assert not (project / "recoloured_images").exists()
    assert load_state(colour_state_path(run_dir)).status == ColourStatus.COMPLETE


def test_colour_apply_gray_world_runs_without_gui(tmp_path: Path, fake_tool_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "project"
    raw = project / "raw_images"
    raw.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(raw / "img1.jpg")
    run_dir = project / "runs" / "gray-run"
    run_dir.mkdir(parents=True)
    undistorted = run_dir / "sfm" / "undistorted" / "images"
    undistorted.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(undistorted / "img1.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        colour_restoration_mode="gray_world",
    )

    def fail_if_gui_launches(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("gray_world must not open the GUI")

    monkeypatch.setattr("reefs.cli.launch_colour_gui", fail_if_gui_launches)

    result = CliRunner().invoke(
        app,
        ["colour", "apply", "--config", str(config), "--run-id", "gray-run"],
    )

    assert result.exit_code == 0, result.output
    assert "complete" in result.output
    assert not colour_state_path(run_dir).exists()
    assert (
        run_dir / "colour_restoration" / "outputs" / "undistorted" / "images" / "img1.jpg"
    ).exists()


def test_colour_open_initialises_state(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    raw = project / "raw_images"
    raw.mkdir(parents=True)
    (raw / "img1.jpg").write_text("", encoding="utf-8")
    (project / "runs" / "colour-run").mkdir(parents=True)
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        colour_restoration_mode="manual",
    )

    result = CliRunner().invoke(
        app,
        ["colour", "open", "--config", str(config), "--run-id", "colour-run", "--no-gui"],
    )

    assert result.exit_code == 0, result.output
    assert colour_state_path(project / "runs" / "colour-run").exists()


def test_colour_apply_reuses_complete_existing_outputs_by_default_and_overwrite_replaces(
    tmp_path: Path, fake_tool_factory
) -> None:
    project = tmp_path / "project"
    raw = project / "raw_images"
    raw.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(raw / "img1.jpg")
    recoloured = project / "recoloured_images"
    recoloured.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(5, 5, 5)).save(recoloured / "img1.jpg")
    run_dir = project / "runs" / "colour-run"
    run_dir.mkdir(parents=True)
    undistorted = run_dir / "sfm" / "undistorted" / "images"
    undistorted.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(undistorted / "img1.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        colour_restoration_mode="manual",
    )
    state = initialise_state(
        run_id="colour-run",
        run_dir=run_dir,
        raw_images=raw,
        recoloured_images=recoloured,
        restoration_mode="manual",
    )
    keyframe = replace(
        rebuild_keyframes(build_image_sequence(raw), count=1)[0],
        edited=True,
        parameters=ColourParameterSet(brightness=0.1),
    )
    save_state(
        colour_state_path(run_dir),
        replace(state.with_status(ColourStatus.COMPLETE, active_session=False), keyframes=[keyframe]),
    )

    reused = CliRunner().invoke(
        app,
        ["colour", "apply", "--config", str(config), "--run-id", "colour-run"],
    )

    assert reused.exit_code == 0, reused.output
    corrected = run_dir / "colour_restoration" / "outputs" / "undistorted" / "images" / "img1.jpg"
    with Image.open(corrected) as image:
        reused_pixel = image.convert("RGB").getpixel((0, 0))
    assert reused_pixel != (5, 5, 5)
    with Image.open(recoloured / "img1.jpg") as image:
        assert image.convert("RGB").getpixel((0, 0)) == (5, 5, 5)

    applied = CliRunner().invoke(
        app,
        ["colour", "apply", "--config", str(config), "--run-id", "colour-run", "--overwrite"],
    )

    assert applied.exit_code == 0, applied.output
    assert "Colour restoration 1/1" in applied.output
    with Image.open(corrected) as image:
        overwritten_pixel = image.convert("RGB").getpixel((0, 0))
    assert overwritten_pixel == reused_pixel


def test_colour_apply_requires_overwrite_for_partial_existing_outputs(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    raw = project / "raw_images"
    raw.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(raw / "img1.jpg")
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(raw / "img2.jpg")
    recoloured = project / "recoloured_images"
    recoloured.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(5, 5, 5)).save(recoloured / "img1.jpg")
    run_dir = project / "runs" / "colour-run"
    run_dir.mkdir(parents=True)
    undistorted = run_dir / "sfm" / "undistorted" / "images"
    undistorted.mkdir(parents=True)
    for name in ["img1.jpg", "img2.jpg"]:
        Image.new("RGB", (8, 6), color=(10, 20, 30)).save(undistorted / name)
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        colour_restoration_mode="manual",
    )
    state = initialise_state(
        run_id="colour-run",
        run_dir=run_dir,
        raw_images=raw,
        recoloured_images=recoloured,
        restoration_mode="manual",
    )
    keyframe = replace(
        rebuild_keyframes(build_image_sequence(raw), count=1)[0],
        edited=True,
        parameters=ColourParameterSet(brightness=0.1),
    )
    save_state(
        colour_state_path(run_dir),
        replace(state.with_status(ColourStatus.COMPLETE, active_session=False), keyframes=[keyframe]),
    )
    partial = run_dir / "colour_restoration" / "outputs" / "undistorted" / "images"
    partial.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(1, 1, 1)).save(partial / "img1.jpg")

    blocked = CliRunner().invoke(
        app,
        ["colour", "apply", "--config", str(config), "--run-id", "colour-run"],
    )

    assert blocked.exit_code != 0
    assert "already exists" in blocked.output


@pytest.mark.parametrize(
    ("choice", "expected_status", "expected_active"),
    [
        ("skip", ColourStatus.SKIPPED, False),
        ("cancel", ColourStatus.CANCELLED, False),
        ("continue", ColourStatus.ACTIVE, True),
    ],
)
def test_colour_open_gui_close_prompt_paths(
    tmp_path: Path,
    fake_tool_factory,
    monkeypatch: pytest.MonkeyPatch,
    choice: str,
    expected_status: ColourStatus,
    expected_active: bool,
) -> None:
    project = tmp_path / "project"
    raw = project / "raw_images"
    raw.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(raw / "img1.jpg")
    (project / "runs" / "colour-run").mkdir(parents=True)
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        colour_restoration_mode="manual",
    )

    def fake_launch(*, state, run_dir, **_: object) -> int:
        ColourGuiController(state=state, run_dir=run_dir).close(choice)
        return 0

    monkeypatch.setattr("reefs.cli.launch_colour_gui", fake_launch)

    result = CliRunner().invoke(
        app,
        ["colour", "open", "--config", str(config), "--run-id", "colour-run"],
    )

    assert result.exit_code == 0, result.output
    state = load_state(colour_state_path(project / "runs" / "colour-run"))
    assert state.status == expected_status
    assert state.active_session is expected_active
