"""Mocked failure-path tests for splat CLI validation."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from tests.conftest import write_config, write_test_jpeg, write_undistorted_sfm_fixture


def _write_project_config(tmp_path: Path, fake_tool_factory) -> tuple[Path, Path]:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
    )
    return project, config


def test_splat_preflight_fails_when_sfm_outputs_are_missing(tmp_path: Path, fake_tool_factory) -> None:
    project, config = _write_project_config(tmp_path, fake_tool_factory)
    (project / "runs" / "old").mkdir(parents=True)

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "old", "--steps", "splat.preflight"],
    )

    assert result.exit_code != 0
    assert "undistorted images directory is missing" in result.output


def test_splat_preflight_succeeds_with_valid_sfm_outputs(tmp_path: Path, fake_tool_factory) -> None:
    project, config = _write_project_config(tmp_path, fake_tool_factory)
    run_dir = project / "runs" / "old"
    run_dir.mkdir(parents=True)
    write_undistorted_sfm_fixture(run_dir)

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "old", "--steps", "splat.preflight"],
    )

    assert result.exit_code == 0, result.output
    status = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))
    assert status["last_completed_stage"] == "splat.preflight"
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["splat_preflight"]["source"]["image_count"] == 1


def test_existing_splat_output_fails_up_front_in_non_interactive_prompt_mode(
    tmp_path: Path, fake_tool_factory
) -> None:
    project, config = _write_project_config(tmp_path, fake_tool_factory)
    run_dir = project / "runs" / "old"
    run_dir.mkdir(parents=True)
    write_undistorted_sfm_fixture(run_dir)
    (run_dir / "splat" / "patches" / "p000").mkdir(parents=True)

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "old", "--steps", "splat.patch"],
    )

    assert result.exit_code != 0
    assert "Existing splat outputs detected in a non-interactive run" in result.output


def test_existing_splat_output_overwrite_deletes_before_stage_is_marked(
    tmp_path: Path, fake_tool_factory
) -> None:
    project, config = _write_project_config(tmp_path, fake_tool_factory)
    run_dir = project / "runs" / "old"
    run_dir.mkdir(parents=True)
    write_undistorted_sfm_fixture(run_dir)
    stale = run_dir / "splat" / "patches" / "p000"
    stale.mkdir(parents=True)
    (stale / "stale.txt").write_text("old", encoding="utf-8")

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
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    assert not (run_dir / "splat" / "patches" / "p000" / "stale.txt").exists()
    assert (run_dir / "splat" / "patches" / "p000" / "patch_metadata.json").exists()
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["splat_preflight"]["output_decisions"][0]["decision"] == "overwrite"
    assert manifest["generated_output_events"][0]["stage"] == "splat.patch"


def test_splat_train_blocks_malformed_patch_metadata_before_lfs(
    tmp_path: Path, fake_tool_factory
) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    marker = tmp_path / "lfs_was_run.txt"
    lfs = tmp_path / "LichtFeld-Studio"
    lfs.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"--version\" || \"$1\" == \"--help\" ]]; then\n"
        "  echo 'LichtFeld Studio v0.5.2'\n"
        "  exit 0\n"
        "fi\n"
        f"touch {marker}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    lfs.chmod(0o755)
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=lfs,
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
    )
    run_dir = project / "runs" / "old"
    run_dir.mkdir(parents=True)
    write_undistorted_sfm_fixture(run_dir)
    patch = run_dir / "splat" / "patches" / "p000"
    patch.mkdir(parents=True)
    (patch / "patch_metadata.json").write_text(
        json.dumps(
            {
                    "patch_id": "p000",
                    "status": "valid",
                    "selected_images": ["image_0001.jpg"],
                    "selected_image_count": 1,
                "bounds": {
                    "min_x": 0,
                    "max_x": 1,
                    "min_y": 0,
                    "max_y": 1,
                    "min_z": 0,
                    "max_z": 1,
                    "buffer": 0.1,
                },
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "old",
            "--steps",
            "splat.train",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code != 0
    assert "selector diagnostics" in result.output
    assert not marker.exists()
