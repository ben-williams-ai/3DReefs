"""Integration checks for colour-aware splat source selection."""

from __future__ import annotations

from pathlib import Path

from reefs.colour.pipeline import colour_state_path
from reefs.colour.state import ColourRestorationState, ColourStatus, save_state
from reefs.config.models import ColourRestorationConfig, PipelineConfig, ProjectConfig, ToolsConfig
from reefs.runs.manifest import create_run_paths
from reefs.splat.validation import validate_splat_source
from tests.conftest import write_test_jpeg, write_undistorted_sfm_fixture


def test_gray_world_splat_source_uses_recoloured_images_and_raw_geometry(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    (runs_dir / "gray").mkdir(parents=True)
    run_paths = create_run_paths(runs_dir, run_id="gray")
    project = tmp_path / "project"
    raw = project / "raw_images"
    recoloured = project / "recoloured_images"
    write_test_jpeg(raw / "image_0001.jpg")
    write_test_jpeg(recoloured / "image_0001.jpg")
    write_undistorted_sfm_fixture(run_paths.run_dir, image_names=["image_0001.jpg"])
    save_state(
        colour_state_path(run_paths.run_dir),
        ColourRestorationState(
            run_id="gray",
            source_raw_root=raw,
            output_recoloured_root=recoloured,
            restoration_mode="gray_world",
            status=ColourStatus.COMPLETE,
            splat_image_source="recoloured",
            splat_images_path=recoloured,
        ),
    )
    config = PipelineConfig(
        colour_restoration=ColourRestorationConfig(mode="gray_world"),
        project=ProjectConfig(dir=project),
        tools=ToolsConfig(),
    )

    result = validate_splat_source(run_paths, config=config)

    assert result.paths.images_dir == recoloured
    assert result.paths.geometry_images_dir == run_paths.run_dir / "sfm" / "undistorted" / "images"
    assert result.paths.sparse_dir == run_paths.run_dir / "sfm" / "undistorted" / "sparse"
