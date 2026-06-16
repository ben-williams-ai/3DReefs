"""Mocked successful splat CLI flows."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from tests.conftest import write_config, write_test_jpeg, write_undistorted_sfm_fixture


def _fake_lfs(path: Path) -> Path:
    path.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"--version\" || \"$1\" == \"--help\" ]]; then\n"
        "  echo 'LichtFeld Studio v0.5.2'\n"
        "  exit 0\n"
        "fi\n"
        "out=''\n"
        "iters='500'\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  case \"$1\" in\n"
        "    -o) out=\"$2\"; shift 2 ;;\n"
        "    -i) iters=\"$2\"; shift 2 ;;\n"
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
        "mkdir -p \"$out\"\n"
        "echo \"${iters}/${iters} | Loss: 0.1 | Splats: 12345\"\n"
        "printf 'ply\\n' > \"$out/splat_${iters}.ply\"\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_splat_patch_generates_patch_dataset(tmp_path: Path, fake_tool_factory) -> None:
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
    patch_dir = run_dir / "splat" / "patches" / "p000"
    assert (patch_dir / "patch_metadata.json").exists()
    metadata = json.loads((patch_dir / "patch_metadata.json").read_text(encoding="utf-8"))
    assert set(["min_x", "max_x", "min_y", "max_y", "min_z", "max_z"]).isdisjoint(metadata)
    assert set(["min_x", "max_x", "min_y", "max_y", "min_z", "max_z", "buffer"]).issubset(metadata["bounds"])
    assert metadata["selector"]["name"] == "target_aware_spatial_greedy"
    assert metadata["selector"]["selected_local_count"] == metadata["selected_local_count"]
    assert metadata["selector"]["selected_support_count"] == metadata["selected_support_count"]
    assert (patch_dir / "sparse" / "0" / "points3D.txt").exists()
    assert (patch_dir / "selected_images" / "image_0001.jpg").is_symlink()
    assert (patch_dir / "patch_diagnostics" / "camera_coverage.csv").exists()
    assert (patch_dir / "patch_diagnostics" / "plot.png").exists()
    assert (patch_dir / "patch_diagnostics" / "plot.html").exists()
    assert (patch_dir / "patch_diagnostics" / "histogram.png").exists()
    assert (run_dir / "splat" / "patches" / "patch_summary.png").exists()
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["splat"]["patches"][0]["status"] == "valid"
    status = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))
    assert status["stage_statuses"]["splat.patch"] == "complete"


def test_splat_train_records_patch_status(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=_fake_lfs(tmp_path / "LichtFeld-Studio"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
    )
    run_dir = project / "runs" / "old"
    run_dir.mkdir(parents=True)
    write_undistorted_sfm_fixture(run_dir)
    patch = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "old", "--steps", "splat.patch", "--resume-policy", "overwrite"],
    )
    assert patch.exit_code == 0, patch.output

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "old",
            "--steps",
            "splat.train",
            "--advanced.splat.train.patch_ids",
            "[p000]",
            "--advanced.splat.train.num_iters",
            "500",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    status = json.loads((run_dir / "splat" / "patches" / "p000" / "splat" / "training_status.json").read_text())
    assert status["status"] == "complete"
    assert status["completed_iterations"] == 500
    assert status["output_file"].endswith("splat_finished.ply")
    assert status["original_output_file"].endswith("splat_500.ply")
    assert (run_dir / "splat" / "patches" / "p000" / "splat" / "splat_finished.ply").is_symlink()
    loss_history = run_dir / "splat" / "patches" / "p000" / "splat" / "loss_history.csv"
    assert loss_history.read_text(encoding="utf-8").splitlines() == [
        "iteration,requested_iterations,loss,splats",
        "500,500,0.1,12345",
    ]
    assert status["loss_history_file"] == str(loss_history)
    assert (run_dir / "logs" / "lfs.log").exists()
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["splat"]["training"][0]["patch_id"] == "p000"


def test_splat_train_resume_reuses_existing_training_status(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    lfs = _fake_lfs(tmp_path / "LichtFeld-Studio")
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
    patch = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "old", "--steps", "splat.patch", "--resume-policy", "overwrite"],
    )
    assert patch.exit_code == 0, patch.output
    train = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "old",
            "--steps",
            "splat.train",
            "--advanced.splat.train.num_iters",
            "500",
            "--resume-policy",
            "overwrite",
        ],
    )
    assert train.exit_code == 0, train.output
    lfs.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"--version\" || \"$1\" == \"--help\" ]]; then echo 'LichtFeld Studio v0.5.2'; exit 0; fi\n"
        "exit 99\n",
        encoding="utf-8",
    )
    lfs.chmod(0o755)

    resumed = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "old",
            "--steps",
            "splat.train",
            "--advanced.splat.train.num_iters",
            "500",
            "--resume-policy",
            "resume",
        ],
    )

    assert resumed.exit_code == 0, resumed.output
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["splat"]["training"][0]["decision"] == "reuse"
