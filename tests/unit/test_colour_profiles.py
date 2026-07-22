"""Colour profile persistence checks."""

from pathlib import Path

from PIL import Image

from reefs.colour.filters import ColourParameterSet
from reefs.colour.interpolation import Keyframe
from reefs.colour.profile import build_profile, load_profile, save_profile


def test_profile_round_trip_has_no_absolute_paths(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    raw.mkdir()
    Image.new("RGB", (8, 6), (10, 20, 30)).save(raw / "one.jpg")
    keyframe = Keyframe(
        id="root:one.jpg",
        relative_path=Path("one.jpg"),
        camera_group="root",
        global_position=1,
        camera_position=1,
        list_index=1,
        parameters=ColourParameterSet(warmth=0.1),
        edited=True,
    )
    profile = build_profile(raw_images=raw, mode="global", keyframes=[keyframe])
    destination = tmp_path / "profile.json"

    save_profile(destination, profile)
    loaded = load_profile(destination)

    assert loaded == profile
    assert str(tmp_path) not in destination.read_text(encoding="utf-8")
