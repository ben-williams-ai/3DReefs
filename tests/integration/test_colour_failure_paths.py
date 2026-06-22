"""Integration tests for safe colour restoration failure handling."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from click.testing import CliRunner
from PIL import Image

from reefs.cli import app
from reefs.colour.filters import ColourParameterSet
from reefs.colour.interpolation import rebuild_keyframes
from reefs.colour.ordering import build_image_sequence
from reefs.colour.pipeline import (
    apply_state_corrections,
    assert_colour_ready_for_handoff,
    colour_state_path,
    initialise_state,
)
from reefs.colour.state import ColourRestorationState, ColourStatus, load_state, save_state
from tests.conftest import write_config


def test_apply_without_edited_keyframes_persists_failed_state(tmp_path: Path) -> None:
    raw = tmp_path / "project" / "raw_images"
    raw.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(raw / "img1.jpg")
    run_dir = tmp_path / "project" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    state = initialise_state(
        run_id="run-1",
        run_dir=run_dir,
        raw_images=raw,
        recoloured_images=tmp_path / "project" / "recoloured_images",
    )
    state = replace(state, keyframes=rebuild_keyframes(build_image_sequence(raw), count=1))
    save_state(colour_state_path(run_dir), state)

    with pytest.raises(ValueError, match="At least one edited keyframe"):
        apply_state_corrections(state=state, run_dir=run_dir)

    failed = load_state(colour_state_path(run_dir))
    assert failed.status == ColourStatus.FAILED
    assert failed.active_session is False
    assert failed.error is not None
    assert "At least one edited keyframe" in failed.error["message"]


def test_partial_apply_failure_records_failing_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = tmp_path / "project" / "raw_images"
    raw.mkdir(parents=True)
    for name in ["img1.jpg", "img2.jpg"]:
        Image.new("RGB", (8, 6), color=(10, 20, 30)).save(raw / name)
    run_dir = tmp_path / "project" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    state = initialise_state(
        run_id="run-1",
        run_dir=run_dir,
        raw_images=raw,
        recoloured_images=tmp_path / "project" / "recoloured_images",
    )
    keyframe = replace(
        rebuild_keyframes(build_image_sequence(raw), count=1)[0],
        edited=True,
        parameters=ColourParameterSet(brightness=0.1),
    )
    state = replace(state, keyframes=[keyframe])
    save_state(colour_state_path(run_dir), state)

    def fail_on_second(*, source: Path, destination: Path, parameters: ColourParameterSet) -> None:
        if source.name == "img2.jpg":
            raise RuntimeError("simulated apply failure")
        destination.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (8, 6), color=(20, 20, 20)).save(destination)

    monkeypatch.setattr("reefs.colour.pipeline.correct_image_file", fail_on_second)

    with pytest.raises(RuntimeError, match="simulated apply failure"):
        apply_state_corrections(state=state, run_dir=run_dir)

    failed = load_state(colour_state_path(run_dir))
    assert failed.status == ColourStatus.FAILED
    assert failed.error is not None
    assert failed.error["failed_image"] == "img2.jpg"


def test_colour_open_reports_gui_launch_failure(
    tmp_path: Path,
    fake_tool_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    raw = project / "raw_images"
    raw.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(raw / "img1.jpg")
    (project / "runs" / "run-1").mkdir(parents=True)
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        recolour_images=True,
    )

    def fail_launch(**_: object) -> int:
        raise RuntimeError("display is unavailable")

    monkeypatch.setattr("reefs.cli.launch_colour_gui", fail_launch)

    result = CliRunner().invoke(app, ["colour", "open", "--config", str(config), "--run-id", "run-1"])

    assert result.exit_code != 0
    assert "display is unavailable" in result.output


def test_partial_corrected_tree_blocks_recoloured_handoff(tmp_path: Path) -> None:
    project = tmp_path / "project"
    raw = project / "raw_images"
    raw.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(raw / "img1.jpg")
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(raw / "img2.jpg")
    recoloured = project / "recoloured_images"
    recoloured.mkdir()
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(recoloured / "img1.jpg")
    run_dir = project / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    save_state(
        colour_state_path(run_dir),
        ColourRestorationState(
            run_id="run-1",
            source_raw_root=raw,
            output_recoloured_root=recoloured,
            status=ColourStatus.COMPLETE,
        ),
    )

    with pytest.raises(ValueError, match="incomplete or inconsistent"):
        assert_colour_ready_for_handoff(run_dir=run_dir, require_complete=True)


def test_pipeline_failure_stops_background_colour_gui_and_preserves_state(
    tmp_path: Path,
    fake_tool_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    raw = project / "raw_images"
    raw.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(raw / "img1.jpg")
    (project / "runs" / "run-1").mkdir(parents=True)
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        recolour_images=True,
    )

    class FakeProcess:
        terminated = False

        def poll(self):
            return None

        def terminate(self) -> None:
            self.terminated = True

        def wait(self, timeout=None):  # noqa: ANN001, ANN202 - subprocess-like fake.
            return 0

        def kill(self) -> None:
            raise AssertionError("terminate should be enough")

    process = FakeProcess()

    def fake_start(**kwargs):
        run_dir = project / "runs" / kwargs["run_id"]
        state = load_state(colour_state_path(run_dir))
        save_state(colour_state_path(run_dir), state.with_status(ColourStatus.ACTIVE, active_session=True))
        return {"mode": "background", "pid": 123}, process

    monkeypatch.setattr("reefs.cli._start_colour_gui_for_pipeline", fake_start)
    monkeypatch.setattr("reefs.cli.validate_tool", lambda **_: (_ for _ in ()).throw(RuntimeError("tool failure")))

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "run-1", "--steps", "foundation", "--resume-policy", "overwrite"],
    )

    assert result.exit_code != 0
    assert process.terminated is True
    state = load_state(colour_state_path(project / "runs" / "run-1"))
    assert state.status == ColourStatus.ACTIVE
    assert state.active_session is False
