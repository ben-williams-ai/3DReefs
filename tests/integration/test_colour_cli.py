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


def test_colour_apply_runs_without_sfm_or_splat(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    raw = project / "raw_images"
    raw.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(raw / "img1.jpg")
    run_dir = project / "runs" / "colour-run"
    run_dir.mkdir(parents=True)
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        recolour_images=True,
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
    assert (project / "recoloured_images" / "img1.jpg").exists()
    assert load_state(colour_state_path(run_dir)).status == ColourStatus.COMPLETE


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
        recolour_images=True,
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
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        recolour_images=True,
    )
    state = initialise_state(
        run_id="colour-run",
        run_dir=run_dir,
        raw_images=raw,
        recoloured_images=recoloured,
    )
    keyframe = replace(
        rebuild_keyframes(build_image_sequence(raw), count=1)[0],
        edited=True,
        parameters=ColourParameterSet(brightness=0.1),
    )
    save_state(colour_state_path(run_dir), replace(state, keyframes=[keyframe]))

    reused = CliRunner().invoke(
        app,
        ["colour", "apply", "--config", str(config), "--run-id", "colour-run"],
    )

    assert reused.exit_code == 0, reused.output
    assert "Found existing complete recoloured_images/ for this dataset" in reused.output
    with Image.open(recoloured / "img1.jpg") as image:
        reused_pixel = image.convert("RGB").getpixel((0, 0))
    assert reused_pixel == (5, 5, 5)

    applied = CliRunner().invoke(
        app,
        ["colour", "apply", "--config", str(config), "--run-id", "colour-run", "--overwrite"],
    )

    assert applied.exit_code == 0, applied.output
    assert "Colour restoration 1/1" in applied.output
    with Image.open(recoloured / "img1.jpg") as image:
        overwritten_pixel = image.convert("RGB").getpixel((0, 0))
    assert overwritten_pixel != reused_pixel


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
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        recolour_images=True,
    )
    state = initialise_state(
        run_id="colour-run",
        run_dir=run_dir,
        raw_images=raw,
        recoloured_images=recoloured,
    )
    keyframe = replace(
        rebuild_keyframes(build_image_sequence(raw), count=1)[0],
        edited=True,
        parameters=ColourParameterSet(brightness=0.1),
    )
    save_state(colour_state_path(run_dir), replace(state, keyframes=[keyframe]))

    blocked = CliRunner().invoke(
        app,
        ["colour", "apply", "--config", str(config), "--run-id", "colour-run"],
    )

    assert blocked.exit_code != 0
    assert "incomplete or inconsistent outputs" in blocked.output
    assert "will be overwritten" in blocked.output


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
        recolour_images=True,
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
