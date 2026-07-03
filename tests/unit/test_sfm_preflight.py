"""Tests for SfM preflight validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from reefs.config.loader import load_config
from reefs.io.paths import derive_project_paths
from reefs.preflight.images import detect_image_layout
from reefs.preflight.sfm import validate_sfm_preflight
from reefs.runs.manifest import create_run_paths
from tests.conftest import write_test_jpeg


def _config(tmp_path: Path, *, vocab: bool = True, recolour: bool = False):
    project = tmp_path / "project"
    project.mkdir()
    vocab_path = tmp_path / "vocab.bin"
    if vocab:
        vocab_path.write_bytes(b"vocab")
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        f"""
colour_restoration:
  mode: {"manual" if recolour else "off"}
  overwrite: false
  start_sfm_immediately: true

project:
  dir: {project}
tools:
  colmap_bin: colmap
  lfs_bin: LichtFeld-Studio
  splat_transform_bin: splat-transform
  vocab_tree_path: {vocab_path if vocab else ''}
""".lstrip(),
        encoding="utf-8",
    )
    return project, load_config(config_path)


def test_missing_vocab_tree_fails_before_matching(tmp_path: Path) -> None:
    project, config = _config(tmp_path, vocab=False)
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    paths = derive_project_paths(config, None)
    layout = detect_image_layout(paths.raw_images)
    run_paths = create_run_paths(paths.runs)

    with pytest.raises(ValueError, match="requires a valid feature-compatible vocabulary tree path"):
        validate_sfm_preflight(config=config, derived_paths=paths, layout=layout, run_paths=run_paths)


def test_aliked_loop_detection_requires_aliked_vocab_tree(tmp_path: Path) -> None:
    project, config = _config(tmp_path, vocab=True)
    config.advanced.sfm.feature_extraction.type = "ALIKED"
    config.advanced.sfm.feature_extraction.aliked.model = "n32"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    paths = derive_project_paths(config, None)
    layout = detect_image_layout(paths.raw_images)
    run_paths = create_run_paths(paths.runs)

    with pytest.raises(ValueError, match="feature_type=ALIKED"):
        validate_sfm_preflight(config=config, derived_paths=paths, layout=layout, run_paths=run_paths)


def test_mixed_dimensions_fail_with_report(tmp_path: Path) -> None:
    project, config = _config(tmp_path)
    write_test_jpeg(project / "raw_images" / "cam1" / "a.jpg", width=64, height=48)
    write_test_jpeg(project / "raw_images" / "cam1" / "b.jpg", width=32, height=48)
    paths = derive_project_paths(config, None)
    layout = detect_image_layout(paths.raw_images)
    run_paths = create_run_paths(paths.runs)

    with pytest.raises(ValueError, match="Image dimensions differ"):
        validate_sfm_preflight(config=config, derived_paths=paths, layout=layout, run_paths=run_paths)
    assert (run_paths.run_dir / "reports" / "image_dimension_report.md").exists()
