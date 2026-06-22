"""Tests for colour GUI prompt text."""

from pathlib import Path

from reefs.colour.filters import ColourParameterSet
from reefs.colour.gui import (
    apply_confirmation_text,
    close_choices,
    completion_message,
    keyframe_row_summary,
    keyframe_saved_values_text,
    overwrite_warning_text,
)
from reefs.colour.interpolation import Keyframe


def test_apply_confirmation_reports_unedited_counts() -> None:
    text = apply_confirmation_text(total_keyframes=10, edited_keyframes=7, total_images=100)

    assert "not corrected 3 keyframes" in text
    assert "all 100 images" in text
    assert "7 edited keyframes" in text


def test_apply_confirmation_when_all_keyframes_edited() -> None:
    assert apply_confirmation_text(total_keyframes=2, edited_keyframes=2, total_images=5) == (
        "Ready to colour correct all 5 images, proceed?"
    )


def test_close_choices_match_required_options() -> None:
    assert close_choices() == (
        "Yes, and cancel job",
        "Yes, progress to SfM without colour restoration",
        "No, continue applying colour restoration",
    )


def test_overwrite_and_completion_messages() -> None:
    assert "overwrite the current corrected version" in overwrite_warning_text()
    assert "already be running" in completion_message(start_sfm_immediately=True)
    assert "can start" in completion_message(start_sfm_immediately=False)


def test_keyframe_row_context_and_saved_values() -> None:
    keyframe = Keyframe(
        id="cam1:img2.jpg",
        relative_path=Path("cam1/img2.jpg"),
        camera_group="cam1",
        global_position=12,
        camera_position=3,
        list_index=2,
        edited=True,
        parameters=ColourParameterSet(brightness=0.2, saturation=1.3),
    )

    assert keyframe_saved_values_text(keyframe) == "edited: saturation=1.3, brightness=0.2"
    summary = keyframe_row_summary(keyframe)
    assert "2. img2.jpg" in summary
    assert "camera: cam1" in summary
    assert "dataset: 12" in summary
    assert "camera pos: 3" in summary
    assert "path: cam1/img2.jpg" in summary
