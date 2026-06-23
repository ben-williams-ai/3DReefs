"""Integration tests for SfM partial-output decisions."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from reefs.io.yaml_json import write_json, write_yaml
from tests.conftest import write_test_jpeg


def _fake_colmap_for_undistort(path: Path) -> Path:
    path.write_text(
        """#!/usr/bin/env python3
import shutil
import sys
from pathlib import Path

args = sys.argv[1:]
if not args or args[0] in {"-h", "--help"}:
    print("COLMAP 4.0.4 with CUDA")
    raise SystemExit(0)
cmd = args[0]
if len(args) > 1 and args[1] in {"-h", "--help"}:
    print(f"help for {cmd}")
    raise SystemExit(0)

def value(flag):
    return args[args.index(flag) + 1]

if cmd == "image_undistorter":
    out = Path(value("--output_path"))
    (out / "images").mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(value("--image_path")) / "image_0001.jpg", out / "images" / "image_0001.jpg")
    (out / "sparse").mkdir(parents=True, exist_ok=True)
    (out / "sparse" / "cameras.txt").write_text("1 OPENCV 64 48 1 1 1 1 0 0 0 0\\n")
else:
    pass
""",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_sfm_partial_run_requires_noninteractive_policy(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    previous = project / "runs" / "old"
    previous.mkdir(parents=True)
    write_json(previous / "run_status.json", {"status": "preflight_failed"})
    write_json(previous / "run_manifest.json", {"requested_steps": ["sfm"]})
    write_yaml(previous / "effective_config.yml", {"project": {"dir": str(project)}})
    config = tmp_path / "config.yml"
    config.write_text(
        f"""
colour_restoration:
  mode: off
  overwrite: false
  start_sfm_immediately: true

project:
  dir: {project}
tools:
  colmap_bin: {fake_tool_factory("colmap", "COLMAP 4.0.4")}
  lfs_bin: {fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")}
  splat_transform_bin: {fake_tool_factory("splat-transform", "splat-transform 1.0")}
""".lstrip(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["--config", str(config), "--steps", "sfm"])

    assert result.exit_code != 0
    assert "non-interactive run" in result.output


def test_sfm_preflight_only_records_specific_stage(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    config = tmp_path / "config.yml"
    config.write_text(
        f"""
colour_restoration:
  mode: off
  overwrite: false
  start_sfm_immediately: true

project:
  dir: {project}
tools:
  colmap_bin: {fake_tool_factory("colmap", "COLMAP 4.0.4")}
  lfs_bin: {fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")}
  splat_transform_bin: {fake_tool_factory("splat-transform", "splat-transform 1.0")}
advanced:
  sfm:
    matching:
      mode: sequential
""".lstrip(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["--config", str(config), "--steps", "sfm.preflight", "--resume-policy", "overwrite"])

    assert result.exit_code == 0, result.output
    run_dir = next((project / "runs").iterdir())
    payload = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))
    assert payload["last_completed_stage"] == "sfm.preflight"
    assert not (run_dir / "sfm" / "sparse").exists()


def test_sfm_undistort_overwrite_uses_existing_run_dir(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    run_dir = project / "runs" / "old"
    selected = run_dir / "sfm" / "selected_sparse"
    selected.mkdir(parents=True)
    for name in ["cameras.txt", "images.txt", "points3D.txt"]:
        (selected / name).write_text("1 OPENCV 64 48 1 1 1 1 0 0 0 0\n", encoding="utf-8")
    partial = run_dir / "sfm" / "undistorted"
    partial.mkdir(parents=True)
    (partial / "stale.txt").write_text("partial", encoding="utf-8")
    config = tmp_path / "config.yml"
    config.write_text(
        f"""
colour_restoration:
  mode: off
  overwrite: false
  start_sfm_immediately: true

project:
  dir: {project}
tools:
  colmap_bin: {_fake_colmap_for_undistort(tmp_path / "colmap")}
  lfs_bin: {fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")}
  splat_transform_bin: {fake_tool_factory("splat-transform", "splat-transform 1.0")}
advanced:
  sfm:
    matching:
      mode: sequential
""".lstrip(),
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
            "sfm.undistort",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    assert [path.name for path in (project / "runs").iterdir()] == ["old"]
    assert not (partial / "stale.txt").exists()
    assert (partial / "images" / "image_0001.jpg").exists()
    payload = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))
    assert payload["last_completed_stage"] == "sfm.undistort"
