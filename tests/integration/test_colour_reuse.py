"""Tests for reusing complete project-level colour restoration outputs."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from reefs.colour.pipeline import (
    adopt_existing_recoloured_images,
    apply_gray_world_restoration,
    colour_state_path,
    initialise_state,
)
from reefs.colour.state import ColourStatus, load_state, save_state


def _write_image(path: Path, *, mode: str = "RGB", size: tuple[int, int] = (8, 6), color: object = (10, 20, 30)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, size, color=color).save(path)


def _state_for_project(project: Path, *, run_id: str = "colour-reuse"):
    run_dir = project / "runs" / run_id
    return run_dir, initialise_state(
        run_id=run_id,
        run_dir=run_dir,
        raw_images=project / "raw_images",
        recoloured_images=project / "recoloured_images",
        restoration_mode="manual",
    )


def test_complete_recoloured_images_are_adopted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_image(project / "raw_images" / "img1.jpg")
    _write_image(project / "recoloured_images" / "img1.jpg", color=(30, 20, 10))
    run_dir, state = _state_for_project(project)

    completed_state = state.with_status(ColourStatus.COMPLETE, active_session=False)

    adopted = adopt_existing_recoloured_images(state=completed_state, run_dir=run_dir)

    assert adopted is not None
    assert adopted.status == ColourStatus.COMPLETE
    assert adopted.active_session is False
    assert adopted.relevant_config["adopted_existing_recoloured_images"] is True
    assert colour_state_path(run_dir).exists()


def test_missing_corrected_image_is_not_adopted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_image(project / "raw_images" / "img1.jpg")
    _write_image(project / "raw_images" / "img2.jpg")
    _write_image(project / "recoloured_images" / "img1.jpg", color=(30, 20, 10))
    run_dir, state = _state_for_project(project)

    completed_state = state.with_status(ColourStatus.COMPLETE, active_session=False)

    assert adopt_existing_recoloured_images(state=completed_state, run_dir=run_dir) is None
    assert not colour_state_path(run_dir).exists()


def test_dimension_mismatch_is_not_adopted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_image(project / "raw_images" / "img1.jpg")
    _write_image(project / "recoloured_images" / "img1.jpg", size=(9, 6), color=(30, 20, 10))
    run_dir, state = _state_for_project(project)

    completed_state = state.with_status(ColourStatus.COMPLETE, active_session=False)

    assert adopt_existing_recoloured_images(state=completed_state, run_dir=run_dir) is None
    assert not colour_state_path(run_dir).exists()


def test_non_rgb_corrected_image_is_not_adopted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_image(project / "raw_images" / "img1.jpg")
    _write_image(project / "recoloured_images" / "img1.jpg", mode="L", color=80)
    run_dir, state = _state_for_project(project)

    completed_state = state.with_status(ColourStatus.COMPLETE, active_session=False)

    assert adopt_existing_recoloured_images(state=completed_state, run_dir=run_dir) is None
    assert not colour_state_path(run_dir).exists()


def test_incomplete_state_does_not_adopt_existing_complete_tree(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_image(project / "raw_images" / "img1.jpg")
    _write_image(project / "recoloured_images" / "img1.jpg", color=(30, 20, 10))
    run_dir, state = _state_for_project(project)

    assert adopt_existing_recoloured_images(state=state, run_dir=run_dir) is None
    assert not colour_state_path(run_dir).exists()


def test_gray_world_reuses_same_run_complete_outputs_and_overwrite_regenerates(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_image(project / "raw_images" / "img1.jpg", color=(10, 20, 30))
    _write_image(project / "recoloured_images" / "img1.jpg", color=(5, 5, 5))
    run_dir, state = _state_for_project(project, run_id="gray")
    state = initialise_state(
        run_id="gray",
        run_dir=run_dir,
        raw_images=project / "raw_images",
        recoloured_images=project / "recoloured_images",
        restoration_mode="gray_world",
    )
    save_state(colour_state_path(run_dir), state.with_status(ColourStatus.COMPLETE, active_session=False))

    reused = apply_gray_world_restoration(state=load_state(colour_state_path(run_dir)), run_dir=run_dir)

    assert reused.relevant_config["adopted_existing_recoloured_images"] is True
    with Image.open(project / "recoloured_images" / "img1.jpg") as image:
        reused_pixel = image.convert("RGB").getpixel((0, 0))
    assert reused_pixel == (5, 5, 5)

    regenerated = apply_gray_world_restoration(
        state=load_state(colour_state_path(run_dir)),
        run_dir=run_dir,
        overwrite_existing=True,
    )

    assert regenerated.status == ColourStatus.COMPLETE
    assert regenerated.relevant_config["regenerated_recoloured_images"] is True
    with Image.open(project / "recoloured_images" / "img1.jpg") as image:
        regenerated_pixel = image.convert("RGB").getpixel((0, 0))
    assert regenerated_pixel != reused_pixel
