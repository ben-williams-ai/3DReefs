"""Tests for keyframe selection and interpolation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from reefs.colour.filters import ColourParameterSet
from reefs.colour.interpolation import interpolate_parameters, rebuild_keyframes
from reefs.colour.ordering import ImageItem, ImageSequence


def _sequence(count: int) -> ImageSequence:
    return ImageSequence(
        source_root=Path("raw_images"),
        ordering_method="natural_path",
        items=[
            ImageItem(
                relative_path=Path(f"img{index}.jpg"),
                camera_group="single",
                global_index=index,
                camera_index=index,
            )
            for index in range(count)
        ],
    )


def test_default_keyframes_are_centred_in_bins() -> None:
    keyframes = rebuild_keyframes(_sequence(1000), count=10)

    assert [keyframe.global_position for keyframe in keyframes] == [
        50,
        150,
        250,
        350,
        450,
        550,
        650,
        750,
        850,
        950,
    ]


def test_rebuild_preserves_existing_saved_edits() -> None:
    sequence = _sequence(10)
    original = rebuild_keyframes(sequence, count=2)
    edited = replace(
        original[0],
        edited=True,
        parameters=ColourParameterSet(brightness=0.25),
    )

    rebuilt = rebuild_keyframes(sequence, count=2, existing=[edited])

    assert rebuilt[0].edited is True
    assert rebuilt[0].parameters == ColourParameterSet(brightness=0.25)


def test_interpolation_clamps_before_and_after_edited_keyframes() -> None:
    sequence = _sequence(5)
    keyframes = rebuild_keyframes(sequence, count=5)
    edited = [
        replace(keyframes[1], edited=True, parameters=ColourParameterSet(brightness=0.0)),
        replace(keyframes[3], edited=True, parameters=ColourParameterSet(brightness=1.0)),
    ]

    interpolated = interpolate_parameters(sequence, edited)

    assert interpolated[Path("img0.jpg")].brightness == 0.0
    assert interpolated[Path("img2.jpg")].brightness == 0.5
    assert interpolated[Path("img4.jpg")].brightness == 1.0


def test_single_edited_keyframe_applies_to_every_image() -> None:
    sequence = _sequence(3)
    keyframe = replace(
        rebuild_keyframes(sequence, count=1)[0],
        edited=True,
        parameters=ColourParameterSet(tint=0.2),
    )

    interpolated = interpolate_parameters(sequence, [keyframe])

    assert {params.tint for params in interpolated.values()} == {0.2}


def test_no_edited_keyframe_fails_clearly() -> None:
    with pytest.raises(ValueError, match="At least one edited keyframe"):
        interpolate_parameters(_sequence(3), [])


def test_per_camera_rebuild_selects_keyframes_per_group() -> None:
    sequence = ImageSequence(
        source_root=Path("raw_images"),
        ordering_method="natural_path",
        items=[
            ImageItem(Path("cam1/img1.jpg"), "cam1", 0, 0),
            ImageItem(Path("cam1/img2.jpg"), "cam1", 1, 1),
            ImageItem(Path("cam2/img1.jpg"), "cam2", 2, 0),
            ImageItem(Path("cam2/img2.jpg"), "cam2", 3, 1),
        ],
    )

    keyframes = rebuild_keyframes(sequence, count=1, per_camera=True)

    assert [keyframe.camera_group for keyframe in keyframes] == ["cam1", "cam2"]
