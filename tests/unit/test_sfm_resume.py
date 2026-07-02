"""Tests for SfM step expansion and overlap helpers."""

from __future__ import annotations

from tests.conftest import write_sparse_text_model, write_test_jpeg
from reefs.sfm.resume import inspect_sfm_outputs, sfm_step_overlaps
from reefs.sfm.validation import expand_sfm_steps, wants_sfm


def test_expand_sfm_steps_contains_default_stages() -> None:
    expanded = expand_sfm_steps(["sfm"])

    assert "sfm.extract" in expanded
    assert "sfm.undistort" in expanded


def test_wants_sfm_detects_sfm_substeps() -> None:
    assert wants_sfm(["foundation"]) is False
    assert wants_sfm(["sfm.preflight"]) is True


def test_sfm_step_overlap_matches_full_sfm_request() -> None:
    assert sfm_step_overlaps("sfm.extract", ["sfm"]) is True
    assert sfm_step_overlaps("sfm.extract", ["splat"]) is False


def test_inspect_sfm_undistort_uses_undistorted_sparse_count(tmp_path) -> None:
    run_dir = tmp_path / "run"
    write_sparse_text_model(
        run_dir / "sfm" / "selected_sparse_txt",
        ["image_0001.jpg", "image_0002.jpg", "unregistered_source_only.jpg"],
    )
    write_sparse_text_model(run_dir / "sfm" / "undistorted" / "sparse", ["image_0001.jpg", "image_0002.jpg"])
    write_test_jpeg(run_dir / "sfm" / "undistorted" / "images" / "image_0001.jpg")
    write_test_jpeg(run_dir / "sfm" / "undistorted" / "images" / "image_0002.jpg")

    states = inspect_sfm_outputs(run_dir)

    assert states["sfm.undistort"]["state"] == "complete"
    assert states["sfm.undistort"]["expected_images"] == 2
    assert states["sfm.undistort"]["undistorted_sparse_images"] == 2


def test_inspect_sfm_undistort_treats_binary_sparse_presence_as_recoverable(tmp_path) -> None:
    run_dir = tmp_path / "run"
    write_sparse_text_model(
        run_dir / "sfm" / "selected_sparse_txt",
        ["image_0001.jpg", "image_0002.jpg", "source_only.jpg"],
    )
    sparse = run_dir / "sfm" / "undistorted" / "sparse"
    sparse.mkdir(parents=True)
    (sparse / "cameras.bin").write_bytes(b"not-empty")
    (sparse / "images.bin").write_bytes(b"not-empty")
    (sparse / "points3D.bin").write_bytes(b"not-empty")
    write_test_jpeg(run_dir / "sfm" / "undistorted" / "images" / "image_0001.jpg")
    write_test_jpeg(run_dir / "sfm" / "undistorted" / "images" / "image_0002.jpg")

    states = inspect_sfm_outputs(run_dir)

    assert states["sfm.undistort"]["state"] == "complete"
    assert states["sfm.undistort"]["expected_images"] == 2
    assert states["sfm.undistort"]["undistorted_sparse_images"] == 2


def test_inspect_sfm_detects_refined_sparse_final(tmp_path) -> None:
    run_dir = tmp_path / "run"
    write_sparse_text_model(run_dir / "sfm" / "refined_sparse" / "final", ["image_0001.jpg", "image_0002.jpg"])

    states = inspect_sfm_outputs(run_dir)

    assert states["sfm.refine"]["state"] == "complete"
    assert states["sfm.refine"]["registered_images"] == 2
