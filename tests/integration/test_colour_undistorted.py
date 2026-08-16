"""Corrected-undistorted workspace integration checks."""

import json
import hashlib
from pathlib import Path

from PIL import Image

from reefs.colour.filters import ColourParameterSet
from reefs.colour.interpolation import Keyframe
from reefs.colour.pipeline import prepare_corrected_workspace
from reefs.colour.profile import build_profile, save_profile


def test_profile_corrects_undistorted_images_atomically(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    workspace = tmp_path / "run" / "sfm" / "undistorted"
    raw.mkdir()
    (workspace / "images").mkdir(parents=True)
    Image.new("RGB", (8, 6), (10, 20, 30)).save(raw / "one.jpg")
    Image.new("RGB", (8, 6), (10, 20, 30)).save(workspace / "images" / "one.jpg")
    keyframe = Keyframe(
        id="root:one.jpg",
        relative_path=Path("one.jpg"),
        camera_group="root",
        global_position=1,
        camera_position=1,
        list_index=1,
        parameters=ColourParameterSet(warmth=0.2),
        edited=True,
    )
    profile_path = tmp_path / "profile.json"
    save_profile(profile_path, build_profile(raw_images=raw, mode="global", keyframes=[keyframe]))

    output = prepare_corrected_workspace(
        run_dir=tmp_path / "run",
        workspace=workspace,
        mode="profile",
        profile_path=profile_path,
        overwrite=False,
    )

    assert output == tmp_path / "run" / "colour_restoration" / "outputs" / "undistorted" / "images"
    assert Image.open(output / "one.jpg").size == (8, 6)
    assert json.loads((output.parent / "manifest.json").read_text())["status"] == "complete"
    assert not (output.parent.parent / ".undistorted.tmp").exists()


def test_profile_reconstructs_verified_legacy_staged_names(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    workspace = tmp_path / "run" / "sfm" / "undistorted"
    (raw / "Cam 1").mkdir(parents=True)
    (workspace / "images").mkdir(parents=True)
    original = Path("Cam 1/Frame One.JPG")
    Image.new("RGB", (8, 6), (10, 20, 30)).save(raw / original)
    Image.new("RGB", (8, 6), (30, 20, 10)).save(raw / "Cam 1/Frame Two.JPG")
    part_hash = hashlib.blake2s(b"Cam 1", digest_size=4).hexdigest()
    name_hash = hashlib.blake2s(original.as_posix().encode(), digest_size=4).hexdigest()
    staged = Path(f"cam_1_{part_hash}/img_000001_{name_hash}.jpg")
    (workspace / "images" / staged).parent.mkdir(parents=True)
    Image.new("RGB", (8, 6), (10, 20, 30)).save(workspace / "images" / staged)
    keyframe = Keyframe(
        id=f"Cam 1:{original.as_posix()}",
        relative_path=original,
        camera_group="Cam 1",
        global_position=1,
        camera_position=1,
        list_index=1,
        parameters=ColourParameterSet(contrast=0.1),
        edited=True,
    )
    profile_path = tmp_path / "profile.json"
    save_profile(profile_path, build_profile(raw_images=raw, mode="global", keyframes=[keyframe]))

    output = prepare_corrected_workspace(
        run_dir=tmp_path / "run",
        workspace=workspace,
        mode="profile",
        profile_path=profile_path,
        overwrite=False,
    )

    assert (output / staged).is_file()
