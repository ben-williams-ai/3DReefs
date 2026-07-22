"""Tests for reusable Stage 2 source-bundle validation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image

from reefs.experiments.ablations.source_bundle import validate_and_write_source_bundle, verify_checksums
from reefs.experiments.ablations.source_job import (
    _patch_has_registered_internal_images,
    build_source_command,
    build_undistortion_recovery_command,
)


def test_source_patch_requires_registered_internal_image(tmp_path: Path) -> None:
    patch = tmp_path / "p000"
    (patch / "sparse" / "0").mkdir(parents=True)
    (patch / "patch_metadata.json").write_text(
        json.dumps({"selected_images": ["internal.jpg", "external.jpg"], "selected_internal_count": 1}),
        encoding="utf-8",
    )
    images = patch / "sparse" / "0" / "images.txt"
    images.write_text("1 1 0 0 0 0 0 0 1 external.jpg\n\n", encoding="utf-8")
    assert not _patch_has_registered_internal_images(patch)
    images.write_text("1 1 0 0 0 0 0 0 1 internal.jpg\n\n", encoding="utf-8")
    assert _patch_has_registered_internal_images(patch)


def _source_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    sfm = run_dir / "sfm"
    sfm.mkdir(parents=True)
    (sfm / "database.db").write_bytes(b"sqlite")
    for model in [sfm / "selected_sparse", sfm / "sparse" / "0"]:
        model.mkdir(parents=True)
        (model / "cameras.txt").write_text("1 PINHOLE 32 24 10 10 16 12\n", encoding="utf-8")
        (model / "images.txt").write_text("1 1 0 0 0 0 0 0 1 a.jpg\n1 2 3\n", encoding="utf-8")
        (model / "points3D.txt").write_text("3 1 2 3 255 255 255 0.1 1 0\n", encoding="utf-8")
    for workspace, size in [
        ("undistorted", (32, 24)),
        ("undistorted_2048", (64, 48)),
        ("undistorted_full_resolution", (96, 72)),
    ]:
        root = run_dir / "sfm" / workspace
        (root / "images").mkdir(parents=True)
        (root / "sparse").mkdir()
        Image.new("RGB", size).save(root / "images" / "a.jpg")
        (root / "sparse" / "cameras.txt").write_text(
            f"1 PINHOLE {size[0]} {size[1]} 10 10 {size[0] / 2} {size[1] / 2}\n",
            encoding="utf-8",
        )
        (root / "sparse" / "images.txt").write_text(
            "1 1 0 0 0 0 0 0 1 a.jpg\n1 2 3\n",
            encoding="utf-8",
        )
        (root / "sparse" / "points3D.txt").write_text(
            "3 1.0 2.0 3.0 255 255 255 0.1 1 0\n",
            encoding="utf-8",
        )
    return run_dir


def test_stage2_source_bundle_validates_three_matching_workspaces(tmp_path: Path) -> None:
    run_dir = _source_run(tmp_path)
    (run_dir / "resource_samples.csv").write_text("timestamp\n", encoding="utf-8")

    manifest = validate_and_write_source_bundle(
        run_dir=run_dir,
        dataset="dataset1",
        source_id="source-test",
        metadata={"git_commit": "abc123", "image_name": "example:image"},
    )

    assert manifest["status"] == "validated"
    assert set(manifest["workspaces"]) == {"1024", "2048", "full"}
    assert manifest["workspaces"]["1024"]["camera_dimensions"][0]["width"] == 32
    assert manifest["workspaces"]["full"]["camera_dimensions"][0]["width"] == 96
    assert (run_dir / "checksums.sha256").is_file()
    assert json.loads((run_dir / "source_manifest.json").read_text(encoding="utf-8"))["source_id"] == "source-test"
    (run_dir / "resource_samples.csv").write_text("timestamp\nlater\n", encoding="utf-8")
    verify_checksums(run_dir)


def test_stage2_source_bundle_rejects_geometry_drift(tmp_path: Path) -> None:
    run_dir = _source_run(tmp_path)
    images = run_dir / "sfm" / "undistorted_2048" / "sparse" / "images.txt"
    images.write_text(images.read_text(encoding="utf-8").replace("0 0 0 1 a.jpg", "1 0 0 1 a.jpg"), encoding="utf-8")

    try:
        validate_and_write_source_bundle(run_dir=run_dir, dataset="dataset1", source_id="source-test")
    except ValueError as exc:
        assert "geometry differs" in str(exc)
        assert "poses_hash" in str(exc)
    else:
        raise AssertionError("expected source pose drift to fail validation")


def test_stage2_source_bundle_checksum_verification_detects_corruption(tmp_path: Path) -> None:
    run_dir = _source_run(tmp_path)
    validate_and_write_source_bundle(run_dir=run_dir, dataset="dataset1", source_id="source-test")
    image = run_dir / "sfm" / "undistorted" / "images" / "a.jpg"
    image.write_bytes(b"corrupt")

    try:
        verify_checksums(run_dir)
    except ValueError as exc:
        assert "checksum mismatch" in str(exc)
    else:
        raise AssertionError("expected source corruption to fail checksum verification")


def test_stage2_source_bundle_can_verify_a_selectively_restored_resolution(tmp_path: Path) -> None:
    run_dir = _source_run(tmp_path)
    validate_and_write_source_bundle(run_dir=run_dir, dataset="dataset1", source_id="source-test")
    shutil.rmtree(run_dir / "sfm" / "undistorted_2048")

    verify_checksums(
        run_dir,
        included_prefixes=["sfm/undistorted", "sfm/undistorted_full_resolution"],
    )


def test_stage2_source_command_is_fixed_to_one_1024_sift_global_sfm_run(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    command = build_source_command(
        repo_root=repo_root,
        ablation_config=repo_root / "experiments" / "ablations" / "ablation_config.yml",
        pipeline_config=repo_root / "configs" / "datasets" / "dataset_01.yml",
        project_dir=tmp_path / "project",
        dataset="dataset1",
        run_id="sfm_dataset1_sfm_1024_sift_global_stage2_source",
    )
    joined = " ".join(command)

    assert "--steps sfm" in joined
    assert "--advanced.sfm.feature_extraction.type SIFT" in joined
    assert "--advanced.sfm.feature_extraction.max_image_size 1024" in joined
    assert "--advanced.sfm.reconstruction.backend global" in joined
    assert "--advanced.sfm.undistortion.additional_max_image_sizes [2048]" in joined
    assert "--advanced.eval.target_image_source full_resolution_undistorted" in joined


def test_stage2_source_recovery_command_runs_only_undistortion(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    command = build_undistortion_recovery_command(
        repo_root=repo_root,
        ablation_config=repo_root / "experiments" / "ablations" / "ablation_config.yml",
        pipeline_config=repo_root / "configs" / "datasets" / "dataset_07.yml",
        project_dir=tmp_path / "project",
        dataset="dataset7",
        run_id="sfm_dataset7_sfm_1024_sift_global_stage2_source_retry2",
    )

    assert command[command.index("--steps") + 1] == "sfm.undistort"
    assert command.count("--steps") == 1
