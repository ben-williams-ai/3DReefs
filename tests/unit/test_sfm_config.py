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
    assert config.advanced.sfm.intrinsics.reconstruction_backend == "incremental"
    assert config.advanced.sfm.matching.mode == "sequential"
    assert config.advanced.sfm.reconstruction.backend == "global"
    assert config.advanced.sfm.feature_extraction.type == "SIFT"
    assert config.advanced.sfm.feature_extraction.sift.domain_size_pooling is True
    assert config.advanced.sfm.undistortion.max_image_size is None
    assert config.advanced.sfm.undistortion.follow_feature_extraction_max_image_size is True
    assert config.advanced.sfm.undistortion.fallback_max_image_size == 4096
    assert config.advanced.sfm.undistortion.additional_max_image_sizes == []
    assert config.advanced.sfm.matching.guided_matching is True
    assert config.advanced.sfm.matching.cross_camera_pairs.enabled is True
    assert config.advanced.sfm.matching.cross_camera_pairs.ordering == "exif_timestamp"
    assert config.advanced.sfm.matching.cross_camera_pairs.index_window == 3
    assert config.advanced.sfm.matching.cross_camera_pairs.run_matching_pass is True
    assert config.advanced.sfm.sparse_refinement.enabled is True
    assert config.advanced.sfm.dense.enabled is False
    assert config.advanced.sfm.dense.patch_match.geom_consistency is False
    assert config.advanced.sfm.dense.mesh.method == "delaunay"
    assert config.advanced.eval.enabled is False
    assert config.advanced.eval.holdout_fraction == 0.10
    assert config.advanced.eval.eval_steps == [5000, 10000, 15000]
    assert config.advanced.eval.metrics == ["psnr", "ssim", "lpips"]
    assert config.advanced.eval.target_image_source == "full_resolution_undistorted"


def test_additional_undistortion_sizes_parse_and_reject_duplicates(tmp_path: Path) -> None:
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
    undistortion:
      additional_max_image_sizes: [2048]
""".lstrip(),
        encoding="utf-8",
    )

    assert load_config(config_path).advanced.sfm.undistortion.additional_max_image_sizes == [2048]

    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace("[2048]", "[2048, 2048]"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicates"):
        load_config(config_path)


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
    assert config.advanced.sfm.sparse_refinement.bundle_adjuster.enabled is False


def test_sparse_refinement_bundle_adjuster_can_be_disabled(tmp_path: Path) -> None:
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
    sparse_refinement:
      enabled: true
      repeats: 2
      bundle_adjuster:
        enabled: false
""".lstrip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.advanced.sfm.sparse_refinement.enabled is True
    assert config.advanced.sfm.sparse_refinement.repeats == 2
    assert config.advanced.sfm.sparse_refinement.bundle_adjuster.enabled is False


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


def test_aliked_feature_options_parse(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        f"""
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
      type: ALIKED
      aliked:
        model: n32
        max_num_features: 4096
        min_score: 0.12
        n32_model_path: {tmp_path / "aliked-n32.onnx"}
""".lstrip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.advanced.sfm.feature_extraction.type == "ALIKED"
    assert config.advanced.sfm.feature_extraction.aliked.model == "n32"
    assert config.advanced.sfm.feature_extraction.aliked.max_num_features == 4096
    assert config.advanced.sfm.feature_extraction.aliked.min_score == 0.12
    assert config.advanced.sfm.feature_extraction.aliked.n32_model_path == tmp_path / "aliked-n32.onnx"
