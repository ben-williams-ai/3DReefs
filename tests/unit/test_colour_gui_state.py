"""Tests for colour GUI state controller."""

from __future__ import annotations

from pathlib import Path

import pytest

from reefs.colour.filters import ColourParameterSet
from reefs.colour.gui import ColourGuiController
from reefs.colour.pipeline import initialise_state
from reefs.colour.state import ColourStatus, load_state


def _state(tmp_path: Path):
    raw = tmp_path / "raw_images"
    raw.mkdir()
    for index in range(4):
        (raw / f"img{index}.jpg").write_text("", encoding="utf-8")
    run_dir = tmp_path / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    return initialise_state(
        run_id="run-1",
        run_dir=run_dir,
        raw_images=raw,
        recoloured_images=tmp_path / "recoloured_images",
    ), run_dir


def test_controller_rebuild_save_delete_and_persist(tmp_path: Path) -> None:
    state, run_dir = _state(tmp_path)
    controller = ColourGuiController(state=state, run_dir=run_dir)

    state = controller.rebuild(keyframe_count=2)
    first_id = state.keyframes[0].id
    controller.save_edit(first_id, ColourParameterSet(brightness=0.2))
    controller.delete_keyframe(state.keyframes[1].id, confirmed=True)

    loaded = load_state(controller.state_path)
    assert loaded.keyframes[0].edited is True
    assert loaded.keyframes[0].parameters == ColourParameterSet(brightness=0.2)
    assert len(loaded.keyframes) == 1


def test_controller_save_edit_allows_repeated_identical_save(tmp_path: Path) -> None:
    state, run_dir = _state(tmp_path)
    controller = ColourGuiController(state=state, run_dir=run_dir)
    state = controller.rebuild(keyframe_count=1)
    keyframe_id = state.keyframes[0].id
    parameters = ColourParameterSet(brightness=0.2)

    controller.save_edit(keyframe_id, parameters)
    saved_again = controller.save_edit(keyframe_id, parameters)

    assert saved_again.keyframes[0].edited is True
    assert saved_again.keyframes[0].parameters == parameters


def test_controller_delete_requires_confirmation(tmp_path: Path) -> None:
    state, run_dir = _state(tmp_path)
    controller = ColourGuiController(state=state, run_dir=run_dir)
    state = controller.rebuild(keyframe_count=1)

    with pytest.raises(ValueError, match="requires confirmation"):
        controller.delete_keyframe(state.keyframes[0].id, confirmed=False)


def test_controller_close_choices_update_status(tmp_path: Path) -> None:
    state, run_dir = _state(tmp_path)
    controller = ColourGuiController(state=state, run_dir=run_dir)

    skipped = controller.close("skip")

    assert skipped.status == ColourStatus.SKIPPED
    assert skipped.active_session is False
