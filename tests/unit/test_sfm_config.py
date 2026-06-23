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
