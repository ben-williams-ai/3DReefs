"""Integration tests for existing splat output decisions."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from reefs.io.yaml_json import write_json
from tests.conftest import write_config, write_test_jpeg, write_undistorted_sfm_fixture


def test_splat_patch_existing_output_fail_policy_stops_before_patch_generation(
    tmp_path: Path, fake_tool_factory
) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
    )
    run_dir = project / "runs" / "old"
    run_dir.mkdir(parents=True)
    write_undistorted_sfm_fixture(run_dir)
    existing = run_dir / "splat" / "patches" / "p000"
    existing.mkdir(parents=True)
    (existing / "sentinel.txt").write_text("keep", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "old",
            "--steps",
            "splat.patch",
            "--resume-policy",
            "fail",
        ],
    )

    assert result.exit_code != 0
    assert "Existing splat outputs require" in result.output
    assert (existing / "sentinel.txt").exists()


def test_splat_patch_resume_fails_when_patch_affecting_config_changed(
    tmp_path: Path, fake_tool_factory
) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
    )
    run_dir = project / "runs" / "old"
    run_dir.mkdir(parents=True)
    write_undistorted_sfm_fixture(run_dir)
    patch = run_dir / "splat" / "patches" / "p000"
    patch.mkdir(parents=True)
    write_json(
        patch / "patch_metadata.json",
        {
            "patch_id": "p000",
            "patch_affecting_config": {"patching": {"max_cameras": 100}},
        },
    )

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "old",
            "--steps",
            "splat.patch",
            "--resume-policy",
            "resume",
        ],
    )

    assert result.exit_code != 0
    assert "Patch-affecting config changed" in result.output
