"""Integration tests for splat outlier filtering."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from tests.conftest import write_config, write_sparse_text_model, write_test_jpeg


def test_splat_outlier_filter_writes_summary(tmp_path: Path, fake_tool_factory) -> None:
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
    image_names = [f"image_{index}.jpg" for index in range(1, 5)]
    for name in image_names:
        write_test_jpeg(run_dir / "sfm" / "undistorted" / "images" / name)
    write_sparse_text_model(run_dir / "sfm" / "undistorted" / "sparse", image_names)

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "old",
            "--steps",
            "splat.outlier_filter",
            "--advanced.splat.outlier_filter.dry_run",
            "true",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads((run_dir / "splat" / "outlier_filter" / "filter_summary.json").read_text(encoding="utf-8"))
    assert summary["state"] in {"complete_no_removals", "dry_run_reported"}
    assert (run_dir / "splat" / "outlier_filter" / "diagnostics" / "camera_pose_top_before.png").exists()
