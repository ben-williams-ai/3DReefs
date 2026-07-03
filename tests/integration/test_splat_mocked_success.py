"""Mocked successful splat CLI flows."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from PIL import Image

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


def _fake_lfs_eval(path: Path) -> Path:
    path.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"--version\" || \"$1\" == \"--help\" ]]; then echo 'LichtFeld Studio v0.5.2'; exit 0; fi\n"
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
        "printf 'iteration,psnr,ssim,lpips,time_per_image,num_gaussians\\n' > \"$out/metrics.csv\"\n"
        "printf '250,20.0,0.60,0.40,0.1,100\\n' >> \"$out/metrics.csv\"\n"
        "printf '%s,21.0,0.70,0.30,0.1,120\\n' \"$iters\" >> \"$out/metrics.csv\"\n"
        "printf 'ply\\n' > \"$out/splat_${iters}.ply\"\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _fake_lfs_eval_failure(path: Path) -> Path:
    path.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"--version\" || \"$1\" == \"--help\" ]]; then echo 'LichtFeld Studio v0.5.2'; exit 0; fi\n"
        "out=''\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  case \"$1\" in\n"
        "    -o) out=\"$2\"; shift 2 ;;\n"
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
        "mkdir -p \"$out\"\n"
        "echo 'eval failed intentionally'\n"
        "exit 1\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _lfs_optimisation_config(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "iterations": 30000,
                "sh_degree_interval": 1000,
                "means_lr": 0.000128,
                "shs_lr": 0.0024,
                "opacity_lr": 0.0335,
                "scaling_lr": 0.00475,
                "rotation_lr": 0.00083,
                "lambda_dssim": 0.2,
                "min_opacity": 0.005,
                "refine_every": 100,
                "start_refine": 500,
                "stop_refine": 25000,
                "grad_threshold": 0.0002,
                "sh_degree": 3,
                "strategy": "mcmc",
                "eval_steps": [7000, 30000],
                "save_steps": [7000, 30000],
                "enable_eval": False,
                "enable_save_eval_images": True,
            }
        ),
        encoding="utf-8",
    )
    return path


def _fake_lfs_retry(path: Path, body: str) -> Path:
    path.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"--version\" || \"$1\" == \"--help\" ]]; then\n"
        "  echo 'LichtFeld Studio v0.5.2'\n"
        "  exit 0\n"
        "fi\n"
        "out=''\n"
        "iters='500'\n"
        "width='full'\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  case \"$1\" in\n"
        "    -o) out=\"$2\"; shift 2 ;;\n"
        "    -i) iters=\"$2\"; shift 2 ;;\n"
        "    --max-width) width=\"$2\"; shift 2 ;;\n"
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
        "mkdir -p \"$out\"\n"
        "printf '%s\\n' \"$width\" >> \"$out/attempt_widths.txt\"\n"
        + body,
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


def test_splat_eval_writes_eval_manifests_and_metrics(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=_fake_lfs_eval(tmp_path / "LichtFeld-Studio"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
    )
    run_dir = project / "runs" / "old"
    run_dir.mkdir(parents=True)
    lfs_config = _lfs_optimisation_config(tmp_path / "lfs_optimisation.json")
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
            "splat.eval",
            "--advanced.eval.enabled",
            "true",
            "--advanced.eval.target_image_source",
            "resized_undistorted",
            "--advanced.eval.eval_steps",
            "[250,500]",
            "--advanced.splat.train.patch_ids",
            "[p000]",
            "--advanced.splat.train.num_iters",
            "500",
            "--advanced.splat.train.lfs_config",
            str(lfs_config),
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    eval_root = run_dir / "splat" / "eval"
    assert (eval_root / "eval_manifest.json").exists()
    assert (eval_root / "datasets" / "p000" / "eval_dataset_manifest.json").exists()
    assert "21.0" in (eval_root / "metrics_final.csv").read_text(encoding="utf-8")
    assert "250" in (eval_root / "metrics_long.csv").read_text(encoding="utf-8")
    status = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))
    assert status["stage_statuses"]["splat.eval"] == "complete"


def test_splat_eval_can_use_full_resolution_undistorted_images(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=_fake_lfs_eval(tmp_path / "LichtFeld-Studio"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
    )
    run_dir = project / "runs" / "old"
    run_dir.mkdir(parents=True)
    lfs_config = _lfs_optimisation_config(tmp_path / "lfs_optimisation.json")
    write_undistorted_sfm_fixture(run_dir)
    full_res = project / "full_resolution_undistorted"
    full_res.mkdir(parents=True)
    Image.new("RGB", (160, 120), color=(1, 2, 3)).save(full_res / "image_0001.jpg")
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
            "splat.eval",
            "--advanced.eval.enabled",
            "true",
            "--advanced.eval.target_image_source",
            "full_resolution_undistorted",
            "--advanced.eval.full_resolution_undistorted_images_dir",
            str(full_res),
            "--advanced.eval.eval_steps",
            "[250,500]",
            "--advanced.splat.train.patch_ids",
            "[p000]",
            "--advanced.splat.train.num_iters",
            "500",
            "--advanced.splat.train.lfs_config",
            str(lfs_config),
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    manifest = json.loads(
        (run_dir / "splat" / "eval" / "datasets" / "p000" / "eval_dataset_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["target_image_source"] == "full_resolution_undistorted"
    assert manifest["uses_patch_training_images"] is False
    assert manifest["is_full_resolution_eval"] is True
    assert manifest["image_source"] == str(full_res)
    assert manifest["holdout_image_dimensions"]["image_0001.jpg"] == {"width": 160, "height": 120}


def test_splat_eval_fails_command_when_lfs_eval_fails(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=_fake_lfs_eval_failure(tmp_path / "LichtFeld-Studio"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
    )
    run_dir = project / "runs" / "old"
    run_dir.mkdir(parents=True)
    lfs_config = _lfs_optimisation_config(tmp_path / "lfs_optimisation.json")
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
            "splat.eval",
            "--advanced.eval.enabled",
            "true",
            "--advanced.eval.target_image_source",
            "resized_undistorted",
            "--advanced.eval.eval_steps",
            "[250,500]",
            "--advanced.splat.train.patch_ids",
            "[p000]",
            "--advanced.splat.train.num_iters",
            "500",
            "--advanced.splat.train.lfs_config",
            str(lfs_config),
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code != 0
    assert "splat.eval failed for patch(es): p000" in result.output
    eval_root = run_dir / "splat" / "eval"
    status = json.loads((eval_root / "patches" / "p000" / "attempt_1" / "eval_status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed"
    manifest = json.loads((eval_root / "eval_manifest.json").read_text(encoding="utf-8"))
    assert manifest["patches"][0]["status"] == "failed"


def test_splat_train_retries_retryable_lfs_width_failure(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    lfs = _fake_lfs_retry(
        tmp_path / "LichtFeld-Studio",
        "if [[ \"$width\" == \"4096\" ]]; then echo 'FastGS CUDA overflow'; exit 1; fi\n"
        "echo \"${iters}/${iters} | Loss: 0.1 | Splats: 12345\"\n"
        "printf 'ply\\n' > \"$out/splat_${iters}.ply\"\n",
    )
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
    patch = CliRunner().invoke(app, ["--config", str(config), "--run-id", "old", "--steps", "splat.patch", "--resume-policy", "overwrite"])
    assert patch.exit_code == 0, patch.output

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "old", "--steps", "splat.train", "--advanced.splat.train.num_iters", "500", "--resume-policy", "overwrite"],
    )

    assert result.exit_code == 0, result.output
    status = json.loads((run_dir / "splat" / "patches" / "p000" / "splat" / "training_status.json").read_text())
    assert status["status"] == "complete"
    assert status["attempted_max_widths"] == [4096, 3000]
    assert [attempt["status"] for attempt in status["attempts"]] == ["failed", "complete"]


def test_splat_train_keeps_warning_without_retry(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    lfs = _fake_lfs_retry(
        tmp_path / "LichtFeld-Studio",
        "echo '450/500 | Loss: 0.1 | Splats: 12345'\n"
        "printf 'ply\\n' > \"$out/splat_450.ply\"\n",
    )
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
    patch = CliRunner().invoke(app, ["--config", str(config), "--run-id", "old", "--steps", "splat.patch", "--resume-policy", "overwrite"])
    assert patch.exit_code == 0, patch.output

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "old", "--steps", "splat.train", "--advanced.splat.train.num_iters", "500", "--resume-policy", "overwrite"],
    )

    assert result.exit_code == 0, result.output
    status = json.loads((run_dir / "splat" / "patches" / "p000" / "splat" / "training_status.json").read_text())
    assert status["status"] == "warning"
    assert status["attempted_max_widths"] == [4096]


def test_splat_train_does_not_retry_unrelated_lfs_failure(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    lfs = _fake_lfs_retry(tmp_path / "LichtFeld-Studio", "echo 'missing images'; exit 1\n")
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
    patch = CliRunner().invoke(app, ["--config", str(config), "--run-id", "old", "--steps", "splat.patch", "--resume-policy", "overwrite"])
    assert patch.exit_code == 0, patch.output

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "old", "--steps", "splat.train", "--advanced.splat.train.num_iters", "500", "--resume-policy", "overwrite"],
    )

    assert result.exit_code == 0, result.output
    status = json.loads((run_dir / "splat" / "patches" / "p000" / "splat" / "training_status.json").read_text())
    assert status["status"] == "failed"
    assert status["attempted_max_widths"] == [4096]
    assert status["retry_skipped_reason"] == "non_retryable_lfs_failure"


def test_splat_train_records_exhausted_retry_widths(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    lfs = _fake_lfs_retry(tmp_path / "LichtFeld-Studio", "echo 'FastGS CUDA overflow'; exit 1\n")
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
    patch = CliRunner().invoke(app, ["--config", str(config), "--run-id", "old", "--steps", "splat.patch", "--resume-policy", "overwrite"])
    assert patch.exit_code == 0, patch.output

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "old", "--steps", "splat.train", "--advanced.splat.train.num_iters", "500", "--resume-policy", "overwrite"],
    )

    assert result.exit_code == 0, result.output
    status = json.loads((run_dir / "splat" / "patches" / "p000" / "splat" / "training_status.json").read_text())
    assert status["status"] == "failed"
    assert status["attempted_max_widths"] == [4096, 3000, 2000, 1000]
    assert status["all_retry_widths_exhausted"] is True


def test_splat_train_empty_retry_width_disables_retry(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    lfs = _fake_lfs_retry(tmp_path / "LichtFeld-Studio", "echo 'FastGS CUDA overflow'; exit 1\n")
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
    patch = CliRunner().invoke(app, ["--config", str(config), "--run-id", "old", "--steps", "splat.patch", "--resume-policy", "overwrite"])
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
            "--advanced.splat.train.num_iters",
            "500",
            "--advanced.splat.train.retry_max_width",
            "[]",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    status = json.loads((run_dir / "splat" / "patches" / "p000" / "splat" / "training_status.json").read_text())
    assert status["status"] == "failed"
    assert status["attempted_max_widths"] == [4096]
    assert status["all_retry_widths_exhausted"] is False


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
