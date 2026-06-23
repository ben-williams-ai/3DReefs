"""Integration tests for applying interpolated colour corrections."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PIL import Image

from reefs.colour.filters import ColourParameterSet
from reefs.colour.interpolation import rebuild_keyframes
from reefs.colour.ordering import build_image_sequence
from reefs.colour.pipeline import apply_gray_world_restoration, apply_state_corrections, colour_state_path, initialise_state
from reefs.colour.state import ColourStatus, load_state, save_state


def test_apply_state_corrections_interpolates_full_dataset_and_records_state(tmp_path: Path) -> None:
    raw = tmp_path / "project" / "raw_images"
    raw.mkdir(parents=True)
    for name, colour in [("img1.jpg", (10, 20, 30)), ("img2.jpg", (20, 30, 40)), ("img10.jpg", (30, 40, 50))]:
        Image.new("RGB", (10, 8), color=colour).save(raw / name)
    run_dir = tmp_path / "project" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    state = initialise_state(
        run_id="run-1",
        run_dir=run_dir,
        raw_images=raw,
        recoloured_images=tmp_path / "project" / "recoloured_images",
    )
    sequence = build_image_sequence(raw)
    keyframes = rebuild_keyframes(sequence, count=3)
    keyframes = [
        replace(keyframes[0], edited=True, parameters=ColourParameterSet(brightness=0.0)),
        keyframes[1],
        replace(keyframes[2], edited=True, parameters=ColourParameterSet(brightness=0.2)),
    ]
    state = replace(state, keyframes=keyframes)
    save_state(colour_state_path(run_dir), state)
    progress: list[tuple[int, int, Path]] = []

    completed = apply_state_corrections(
        state=state,
        run_dir=run_dir,
        progress=lambda index, total, path: progress.append((index, total, path)),
    )

    assert completed.status == ColourStatus.COMPLETE
    assert [path.name for _, _, path in progress] == ["img1.jpg", "img2.jpg", "img10.jpg"]
    for relative_path in sequence.relative_paths:
        output = state.output_recoloured_root / relative_path
        assert output.exists()
        with Image.open(output) as image:
            assert image.size == (10, 8)
            assert image.mode == "RGB"
    persisted = load_state(colour_state_path(run_dir))
    assert persisted.interpolation["total_images"] == 3
    assert persisted.interpolation["edited_keyframes"] == 2
    assert persisted.interpolation["unedited_keyframes"] == 1
    assert persisted.interpolation["output_validation"]["missing"] == []


def test_apply_gray_world_restoration_writes_complete_rgb_tree_and_state(tmp_path: Path) -> None:
    raw = tmp_path / "project" / "raw_images"
    raw.mkdir(parents=True)
    Image.new("RGB", (10, 8), color=(10, 20, 30)).save(raw / "img1.jpg")
    Image.new("L", (10, 8), color=80).save(raw / "img2.png")
    run_dir = tmp_path / "project" / "runs" / "gray"
    run_dir.mkdir(parents=True)
    state = initialise_state(
        run_id="gray",
        run_dir=run_dir,
        raw_images=raw,
        recoloured_images=tmp_path / "project" / "recoloured_images",
        restoration_mode="gray_world",
    )
    progress: list[Path] = []

    completed = apply_gray_world_restoration(
        state=state,
        run_dir=run_dir,
        progress=lambda _index, _total, path: progress.append(path),
    )

    assert completed.status == ColourStatus.COMPLETE
    assert completed.restoration_mode == "gray_world"
    assert completed.sfm_image_source == "raw"
    assert completed.splat_image_source == "recoloured"
    assert [path.name for path in progress] == ["img1.jpg", "img2.png"]
    for name in ["img1.jpg", "img2.png"]:
        with Image.open(state.output_recoloured_root / name) as image:
            assert image.size == (10, 8)
            assert image.mode == "RGB"
    persisted = load_state(colour_state_path(run_dir))
    assert persisted.interpolation["gray_world"] == 1.0
    assert persisted.interpolation["output_validation"]["missing"] == []
