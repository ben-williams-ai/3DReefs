"""Tests for colour GUI prompt text."""

from pathlib import Path

from reefs.colour.filters import ColourParameterSet
from reefs.colour.gui import (
    PARAMETER_CONTROL_SPECS,
    apply_confirmation_text,
    close_choices,
    completion_message,
    keyframe_row_summary,
    keyframe_row_style,
    keyframe_saved_values_text,
    overwrite_warning_text,
    skip_colour_confirmation_text,
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


def test_skip_colour_confirmation_warns_pipeline_will_continue() -> None:
    text = skip_colour_confirmation_text()

    assert "close the GUI" in text
    assert "progress the pipeline without colour correction" in text
    assert "Are you sure?" in text


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
    assert "2. cam1" in summary
    assert "dataset 12" in summary
    assert "camera 3" in summary
    assert "path: cam1/img2.jpg" in summary


def test_parameter_slider_ranges_match_wildflow_clamps() -> None:
    assert PARAMETER_CONTROL_SPECS["gray_world"].minimum == 0.0
    assert PARAMETER_CONTROL_SPECS["gray_world"].maximum == 1.0
    assert PARAMETER_CONTROL_SPECS["warmth"].minimum == -4.0
    assert PARAMETER_CONTROL_SPECS["warmth"].maximum == 4.0
    assert PARAMETER_CONTROL_SPECS["saturation"].maximum == 3.0
    assert PARAMETER_CONTROL_SPECS["brightness"].minimum == -1.0
    assert PARAMETER_CONTROL_SPECS["contrast"].maximum == 1.0
    assert PARAMETER_CONTROL_SPECS["dehaze_omega"].minimum == 0.1


def test_keyframe_row_style_highlights_edited_and_selected_rows() -> None:
    assert "#bfe8c3" in keyframe_row_style(edited=True, selected=False)
    assert "#8fd99b" in keyframe_row_style(edited=True, selected=True)
    assert "#e8f0ff" in keyframe_row_style(edited=False, selected=True)
