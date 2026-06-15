"""Tests for splat source reconstruction validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from reefs.runs.manifest import create_run_paths
from reefs.splat.validation import validate_splat_source
from tests.conftest import write_sparse_text_model, write_test_jpeg, write_undistorted_sfm_fixture


def test_validate_splat_source_accepts_undistorted_sfm_outputs(tmp_path: Path) -> None:
    run_paths = create_run_paths(tmp_path / "runs")
    write_undistorted_sfm_fixture(run_paths.run_dir, image_names=["cam1/image_0001.jpg", "cam1/image_0002.jpg"])

    result = validate_splat_source(run_paths)

    assert result.image_count == 2
    assert result.sparse_image_count == 2
    assert result.point_count == 1
    assert result.paths.images_dir == run_paths.run_dir / "sfm" / "undistorted" / "images"


def test_validate_splat_source_rejects_missing_undistorted_images(tmp_path: Path) -> None:
    run_paths = create_run_paths(tmp_path / "runs")

    with pytest.raises(ValueError, match="undistorted images directory is missing"):
        validate_splat_source(run_paths)


def test_validate_splat_source_rejects_sparse_missing_registered_image(tmp_path: Path) -> None:
    run_paths = create_run_paths(tmp_path / "runs")
    write_test_jpeg(run_paths.run_dir / "sfm" / "undistorted" / "images" / "image_0001.jpg")
    write_sparse_text_model(run_paths.run_dir / "sfm" / "undistorted" / "sparse", ["image_0002.jpg"])

    with pytest.raises(ValueError, match="references undistorted images that are missing"):
        validate_splat_source(run_paths)


def test_validate_splat_source_warns_for_extra_unregistered_images(tmp_path: Path) -> None:
    run_paths = create_run_paths(tmp_path / "runs")
    write_undistorted_sfm_fixture(run_paths.run_dir, image_names=["image_0001.jpg"])
    write_test_jpeg(run_paths.run_dir / "sfm" / "undistorted" / "images" / "extra.jpg")

    result = validate_splat_source(run_paths)

    assert result.warnings
    assert "extra.jpg" in result.warnings[0]
