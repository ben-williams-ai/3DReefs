"""Tests for SfM configuration models."""

from __future__ import annotations

from pathlib import Path

import pytest

from reefs.config.loader import load_config


def test_sfm_defaults_are_available(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
colour_restoration:
  mode: off
  overwrite: false
  start_sfm_immediately: true

project:
  dir: /tmp/example
tools:
  colmap_bin: colmap
  lfs_bin: LichtFeld-Studio
  splat_transform_bin: splat-transform
""".lstrip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.advanced.sfm.intrinsics.camera_model == "OPENCV"
    assert config.advanced.sfm.matching.mode == "sequential_vocab_tree"
    assert config.advanced.sfm.reconstruction.backend == "global"
    assert config.advanced.sfm.feature_extraction.sift.domain_size_pooling is False
    assert config.advanced.sfm.matching.guided_matching is False
    assert config.advanced.sfm.matching.cross_camera_pairs.enabled is False
    assert config.advanced.sfm.matching.cross_camera_pairs.ordering == "exif_timestamp"
    assert config.advanced.sfm.sparse_refinement.enabled is False
    assert config.advanced.sfm.dense.enabled is False
    assert config.advanced.sfm.dense.patch_match.geom_consistency is False
    assert config.advanced.sfm.dense.mesh.method == "delaunay"


def test_mesh_requires_dense_enabled(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
colour_restoration:
  mode: off
  overwrite: false
  start_sfm_immediately: true

project:
  dir: /tmp/example
tools:
  colmap_bin: colmap
  lfs_bin: LichtFeld-Studio
  splat_transform_bin: splat-transform
advanced:
  sfm:
    dense:
      enabled: false
      mesh:
        enabled: true
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires advanced.sfm.dense.enabled"):
        load_config(config_path)


def test_aims_style_sfm_options_parse(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
colour_restoration:
  mode: off
  overwrite: false
  start_sfm_immediately: true

project:
  dir: /tmp/example
tools:
  colmap_bin: colmap
  lfs_bin: LichtFeld-Studio
  splat_transform_bin: splat-transform
advanced:
  sfm:
    feature_extraction:
      sift:
        domain_size_pooling: true
    matching:
      guided_matching: true
      sequential:
        overlap: 30
      cross_camera_pairs:
        enabled: true
        ordering: filename
        index_window: 1
        run_matching_pass: false
    sparse_refinement:
      enabled: true
      repeats: 2
      point_filtering:
        max_reproj_error: 3.0
""".lstrip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.advanced.sfm.feature_extraction.sift.domain_size_pooling is True
    assert config.advanced.sfm.matching.guided_matching is True
    assert config.advanced.sfm.matching.sequential.overlap == 30
    assert config.advanced.sfm.matching.cross_camera_pairs.enabled is True
    assert config.advanced.sfm.matching.cross_camera_pairs.ordering == "filename"
    assert config.advanced.sfm.sparse_refinement.enabled is True
    assert config.advanced.sfm.sparse_refinement.repeats == 2
    assert config.advanced.sfm.sparse_refinement.point_filtering.max_reproj_error == 3.0


def test_cross_camera_pair_ordering_rejects_invalid_value(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
colour_restoration:
  mode: off
  overwrite: false
  start_sfm_immediately: true

project:
  dir: /tmp/example
tools:
  colmap_bin: colmap
  lfs_bin: LichtFeld-Studio
  splat_transform_bin: splat-transform
advanced:
  sfm:
    matching:
      cross_camera_pairs:
        ordering: random
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Config validation failed"):
        load_config(config_path)
