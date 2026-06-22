"""Tests for persisted colour restoration state."""

from __future__ import annotations

from pathlib import Path

from reefs.colour.state import ColourRestorationState, ColourStatus, load_state, save_state


def test_colour_state_save_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "run" / "colour_restoration" / "state.json"
    state = ColourRestorationState(
        run_id="run-1",
        source_raw_root=tmp_path / "raw_images",
        output_recoloured_root=tmp_path / "recoloured_images",
    )

    save_state(path, state)
    loaded = load_state(path)

    assert loaded.run_id == "run-1"
    assert loaded.source_raw_root == tmp_path / "raw_images"
    assert loaded.output_recoloured_root == tmp_path / "recoloured_images"


def test_colour_state_status_transition_updates_session_and_timestamp(tmp_path: Path) -> None:
    state = ColourRestorationState(
        run_id="run-1",
        source_raw_root=tmp_path / "raw_images",
        output_recoloured_root=tmp_path / "recoloured_images",
    )

    active = state.with_status(ColourStatus.ACTIVE, active_session=True)

    assert active.status == ColourStatus.ACTIVE
    assert active.active_session is True
    assert active.updated_at != ""
