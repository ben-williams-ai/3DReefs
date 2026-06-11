"""Mocked integration test for the SfM CLI path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from reefs.cli import app
from tests.conftest import write_test_jpeg


def _fake_colmap(path: Path) -> Path:
    path.write_text(
        """#!/usr/bin/env python3
import os
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

if cmd == "feature_extractor":
    Path(value("--database_path")).parent.mkdir(parents=True, exist_ok=True)
    Path(value("--database_path")).write_bytes(b"sqlite")
elif cmd.endswith("_matcher"):
    pass
elif cmd in {"global_mapper", "mapper"}:
    out = Path(value("--output_path")) / "0"
    out.mkdir(parents=True, exist_ok=True)
    (out / "cameras.txt").write_text("1 OPENCV 64 48 1 1 1 1 0 0 0 0\\n")
    (out / "images.txt").write_text(
        "1 1 0 0 0 0 0 0 1 cam1/a.jpg\\n\\n2 1 0 0 0 1 0 0 1 cam2/a.jpg\\n\\n"
    )
    (out / "points3D.txt").write_text("1 0 0 0 255 255 255 1 1 0\\n")
elif cmd == "model_converter":
    inp = Path(value("--input_path"))
    out = Path(value("--output_path"))
    out.mkdir(parents=True, exist_ok=True)
    for name in ["cameras.txt", "images.txt", "points3D.txt"]:
        shutil.copy2(inp / name, out / name)
elif cmd == "image_undistorter":
    out = Path(value("--output_path"))
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "sparse").mkdir(parents=True, exist_ok=True)
    (out / "sparse" / "cameras.txt").write_text("1 OPENCV 64 48 1 1 1 1 0 0 0 0\\n")
else:
    print(f"unexpected command {cmd}", file=sys.stderr)
    raise SystemExit(2)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_sfm_cli_with_mocked_colmap(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "cam1" / "a.jpg")
    write_test_jpeg(project / "raw_images" / "cam2" / "a.jpg")
    vocab = tmp_path / "vocab.bin"
    vocab.write_bytes(b"vocab")
    colmap = _fake_colmap(tmp_path / "colmap")
    config = tmp_path / "config.yml"
    config.write_text(
        f"""
project:
  dir: {project}
tools:
  colmap_bin: {colmap}
  lfs_bin: {fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")}
  splat_transform_bin: {fake_tool_factory("splat-transform", "splat-transform 1.0")}
  vocab_tree_path: {vocab}
""".lstrip(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["--config", str(config), "--steps", "sfm", "--resume-policy", "overwrite"])

    assert result.exit_code == 0, result.output
    run_dir = next((project / "runs").iterdir())
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["sfm"]["selected_sparse_model"]["registered_images"] == 2
    assert Path(manifest["sfm"]["output_paths"]["undistorted_images"]).exists()
    assert (run_dir / "logs" / "colmap.log").exists()


def test_sfm_can_run_single_vocab_tree_matching_pass(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "cam1" / "a.jpg")
    write_test_jpeg(project / "raw_images" / "cam2" / "a.jpg")
    run_dir = project / "runs" / "old"
    (run_dir / "sfm").mkdir(parents=True)
    (run_dir / "sfm" / "database.db").write_bytes(b"sqlite")
    vocab = tmp_path / "vocab.bin"
    vocab.write_bytes(b"vocab")
    colmap = _fake_colmap(tmp_path / "colmap")
    config = tmp_path / "config.yml"
    config.write_text(
        f"""
project:
  dir: {project}
tools:
  colmap_bin: {colmap}
  lfs_bin: {fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")}
  splat_transform_bin: {fake_tool_factory("splat-transform", "splat-transform 1.0")}
  vocab_tree_path: {vocab}
advanced:
  sfm:
    intrinsics:
      precalculate: false
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
            "sfm.match.vocab_tree",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    colmap_log = (run_dir / "logs" / "colmap.log").read_text(encoding="utf-8")
    assert "vocab_tree_matcher" in colmap_log
    assert "sequential_matcher" not in colmap_log
    status = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))
    assert status["last_completed_stage"] == "sfm.match.vocab_tree"


@pytest.mark.parametrize(
    ("requested_step", "expected_command", "unexpected_commands", "last_stage"),
    [
        ("sfm.extract", "feature_extractor", ["sequential_matcher", "vocab_tree_matcher", "global_mapper"], "sfm.extract"),
        ("sfm.match.sequential", "sequential_matcher", ["feature_extractor", "vocab_tree_matcher", "global_mapper"], "sfm.match.sequential"),
        ("sfm.match.vocab_tree", "vocab_tree_matcher", ["feature_extractor", "sequential_matcher", "global_mapper"], "sfm.match.vocab_tree"),
    ],
)
def test_sfm_can_run_individual_database_stages(
    tmp_path: Path,
    fake_tool_factory,
    requested_step: str,
    expected_command: str,
    unexpected_commands: list[str],
    last_stage: str,
) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "cam1" / "a.jpg")
    write_test_jpeg(project / "raw_images" / "cam2" / "a.jpg")
    run_dir = project / "runs" / "old"
    (run_dir / "sfm").mkdir(parents=True)
    if requested_step.startswith("sfm.match"):
        (run_dir / "sfm" / "database.db").write_bytes(b"sqlite")
    vocab = tmp_path / "vocab.bin"
    vocab.write_bytes(b"vocab")
    colmap = _fake_colmap(tmp_path / "colmap")
    config = tmp_path / "config.yml"
    config.write_text(
        f"""
project:
  dir: {project}
tools:
  colmap_bin: {colmap}
  lfs_bin: {fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")}
  splat_transform_bin: {fake_tool_factory("splat-transform", "splat-transform 1.0")}
  vocab_tree_path: {vocab}
advanced:
  sfm:
    intrinsics:
      precalculate: false
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
            requested_step,
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    colmap_log = (run_dir / "logs" / "colmap.log").read_text(encoding="utf-8")
    assert expected_command in colmap_log
    for unexpected_command in unexpected_commands:
        assert unexpected_command not in colmap_log
    status = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))
    assert status["last_completed_stage"] == last_stage


def test_sfm_reconstruct_overwrite_clears_generated_sparse_outputs(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "cam1" / "a.jpg")
    write_test_jpeg(project / "raw_images" / "cam2" / "a.jpg")
    run_dir = project / "runs" / "old"
    (run_dir / "sfm").mkdir(parents=True)
    (run_dir / "sfm" / "database.db").write_bytes(b"sqlite")
    stale = run_dir / "sfm" / "selected_sparse" / "stale.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("old", encoding="utf-8")
    vocab = tmp_path / "vocab.bin"
    vocab.write_bytes(b"vocab")
    colmap = _fake_colmap(tmp_path / "colmap")
    config = tmp_path / "config.yml"
    config.write_text(
        f"""
project:
  dir: {project}
tools:
  colmap_bin: {colmap}
  lfs_bin: {fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")}
  splat_transform_bin: {fake_tool_factory("splat-transform", "splat-transform 1.0")}
  vocab_tree_path: {vocab}
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
            "sfm.reconstruct",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    assert not stale.exists()
    assert (run_dir / "sfm" / "selected_sparse" / "cameras.txt").exists()
    status = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))
    assert status["last_completed_stage"] == "sfm.reconstruct"


def test_sfm_later_stage_fails_when_database_missing(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "cam1" / "a.jpg")
    write_test_jpeg(project / "raw_images" / "cam2" / "a.jpg")
    run_dir = project / "runs" / "old"
    (run_dir / "sfm").mkdir(parents=True)
    vocab = tmp_path / "vocab.bin"
    vocab.write_bytes(b"vocab")
    config = tmp_path / "config.yml"
    config.write_text(
        f"""
project:
  dir: {project}
tools:
  colmap_bin: {_fake_colmap(tmp_path / "colmap")}
  lfs_bin: {fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")}
  splat_transform_bin: {fake_tool_factory("splat-transform", "splat-transform 1.0")}
  vocab_tree_path: {vocab}
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
            "sfm.match.sequential",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code != 0
    assert "required COLMAP database is missing" in result.output
