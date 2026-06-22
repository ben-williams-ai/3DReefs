"""Tests for colour filter parameter helpers."""

from __future__ import annotations

from reefs.colour.filters import ColourDevice, ColourParameterSet, FILTER_ORDER, select_colour_device


def test_neutral_colour_parameter_defaults() -> None:
    params = ColourParameterSet()

    assert params.gray_world == 0.0
    assert params.warmth == 0.0
    assert params.tint == 0.0
    assert params.saturation == 1.0
    assert params.blue_reduction == 0.0
    assert params.brightness == 0.0
    assert params.contrast == 0.0
    assert params.shadows == 0.0
    assert params.blacks == 0.0
    assert params.highlights == 0.0
    assert params.dehaze_strength == 0.0
    assert params.dehaze_omega == 0.9


def test_filter_order_matches_wildflow_source_order() -> None:
    assert FILTER_ORDER == (
        "gray_world",
        "warmth",
        "tint",
        "saturation",
        "blue_reduction",
        "brightness_contrast",
        "shadows",
        "blacks",
        "highlights",
        "dehaze",
    )


def test_colour_device_falls_back_to_cpu_without_acceleration() -> None:
    device, message = select_colour_device(prefer_acceleration=False)

    assert device == ColourDevice.CPU
    assert "CPU" in message
