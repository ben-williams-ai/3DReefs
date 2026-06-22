"""Tests for reusing complete project-level colour restoration outputs."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from reefs.colour.pipeline import adopt_existing_recoloured_images, colour_state_path, initialise_state
from reefs.colour.state import ColourStatus


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
    )


def test_complete_recoloured_images_are_adopted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_image(project / "raw_images" / "img1.jpg")
    _write_image(project / "recoloured_images" / "img1.jpg", color=(30, 20, 10))
    run_dir, state = _state_for_project(project)

    adopted = adopt_existing_recoloured_images(state=state, run_dir=run_dir)

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

    assert adopt_existing_recoloured_images(state=state, run_dir=run_dir) is None
    assert not colour_state_path(run_dir).exists()


def test_dimension_mismatch_is_not_adopted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_image(project / "raw_images" / "img1.jpg")
    _write_image(project / "recoloured_images" / "img1.jpg", size=(9, 6), color=(30, 20, 10))
    run_dir, state = _state_for_project(project)

    assert adopt_existing_recoloured_images(state=state, run_dir=run_dir) is None
    assert not colour_state_path(run_dir).exists()


def test_non_rgb_corrected_image_is_not_adopted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_image(project / "raw_images" / "img1.jpg")
    _write_image(project / "recoloured_images" / "img1.jpg", mode="L", color=80)
    run_dir, state = _state_for_project(project)

    assert adopt_existing_recoloured_images(state=state, run_dir=run_dir) is None
    assert not colour_state_path(run_dir).exists()
