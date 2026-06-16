"""Tests for Feature 3 splat configuration models."""

from __future__ import annotations

from pathlib import Path

import pytest

from reefs.config.loader import load_config


def _write_minimal_config(path: Path, splat_yaml: str = "") -> Path:
    path.write_text(
        f"""
project:
  dir: /tmp/example
tools:
  colmap_bin: colmap
  lfs_bin: LichtFeld-Studio
  splat_transform_bin: splat-transform
advanced:
  splat:
{splat_yaml or "    {}"}
""".lstrip(),
        encoding="utf-8",
    )
    return path


def test_splat_defaults_are_available(tmp_path: Path) -> None:
    config = load_config(_write_minimal_config(tmp_path / "config.yml"))

    assert config.advanced.splat.outlier_filter.enabled is True
    assert config.advanced.splat.outlier_filter.method == "iqr"
    assert config.advanced.splat.outlier_filter.iqr_mult == 3.0
    assert config.advanced.splat.outlier_filter.max_removal_fraction == 0.05
    assert config.advanced.splat.patching.max_cameras == 800
    assert config.advanced.splat.patching.buffer == 0.1
    assert config.advanced.splat.patching.mode == "view_based"
    assert config.advanced.splat.train.num_iters == 30000
    assert config.advanced.splat.train.num_splats_per_patch == 1_500_000
    assert config.advanced.splat.train.headless is True
    assert config.advanced.splat.cleanup.enabled is True
    assert config.advanced.splat.cleanup.max_area == 0.004
    assert config.advanced.splat.cleanup.min_neighbors == 20
    assert config.advanced.splat.cleanup.radius == 0.05
    assert config.advanced.splat.cleanup.filter_boundaries is True
    assert config.advanced.splat.cleanup.boundary_buffer == 0.1
    assert config.advanced.splat.merge.enabled is True
    assert config.advanced.splat.merge.require_cleaned is True
    assert config.advanced.splat.merge.output_name == "merged_splat.ply"
    assert config.advanced.splat.sog.enabled is True
    assert config.advanced.splat.sog.filter_harmonics == 2


def test_splat_rejects_invalid_patch_limits(tmp_path: Path) -> None:
    config_path = _write_minimal_config(
        tmp_path / "config.yml",
        """
    patching:
      max_cameras: 0
""",
    )

    with pytest.raises(ValueError, match="greater than 0"):
        load_config(config_path)


def test_splat_parses_cli_style_patch_lists(tmp_path: Path) -> None:
    config_path = _write_minimal_config(
        tmp_path / "config.yml",
        """
    patching:
      patch_ids: "[p000,p005]"
    train:
      patch_ids: "[p001, p002]"
""",
    )

    config = load_config(config_path)

    assert config.advanced.splat.patching.patch_ids == ["p000", "p005"]
    assert config.advanced.splat.train.patch_ids == ["p001", "p002"]


def test_splat_parses_postprocess_patch_lists(tmp_path: Path) -> None:
    config_path = _write_minimal_config(
        tmp_path / "config.yml",
        """
    cleanup:
      patch_ids: "[p000,p005]"
    merge:
      patch_ids: "[p001, p002]"
""",
    )

    config = load_config(config_path)

    assert config.advanced.splat.cleanup.patch_ids == ["p000", "p005"]
    assert config.advanced.splat.merge.patch_ids == ["p001", "p002"]


def test_splat_rejects_cleanup_backend_setting(tmp_path: Path) -> None:
    config_path = _write_minimal_config(
        tmp_path / "config.yml",
        """
    cleanup:
      backend: splat_transform
""",
    )

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        load_config(config_path)


def test_splat_rejects_multi_patch_concurrency_setting(tmp_path: Path) -> None:
    config_path = _write_minimal_config(
        tmp_path / "config.yml",
        """
    train:
      concurrency: 2
""",
    )

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        load_config(config_path)
