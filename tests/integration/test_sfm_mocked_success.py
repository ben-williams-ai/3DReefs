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
import sqlite3
import struct
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

def image_names(image_root):
    root = Path(image_root)
    names = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}:
            names.append(path.relative_to(root).as_posix())
    return names

def camera_group(name):
    parts = Path(name).parts
    return parts[0] if len(parts) > 1 else "single"

def params_blob(values):
    return sqlite3.Binary(struct.pack("<8d", *values))

def create_database(database_path, image_root):
    database = Path(database_path)
    database.parent.mkdir(parents=True, exist_ok=True)
    names = image_names(image_root)
    groups = sorted({camera_group(name) for name in names})
    camera_ids = {group: index for index, group in enumerate(groups, start=1)}
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE cameras (camera_id INTEGER PRIMARY KEY, model INTEGER, width INTEGER, height INTEGER, params BLOB, prior_focal_length INTEGER)"
        )
        connection.execute(
            "CREATE TABLE images (image_id INTEGER PRIMARY KEY, name TEXT, camera_id INTEGER)"
        )
        for group, camera_id in camera_ids.items():
            connection.execute(
                "INSERT INTO cameras VALUES (?, ?, ?, ?, ?, ?)",
                (camera_id, 4, 64, 48, params_blob([0, 0, 0, 0, 0, 0, 0, 0]), 0),
            )
        for image_id, name in enumerate(names, start=1):
            connection.execute(
                "INSERT INTO images VALUES (?, ?, ?)",
                (image_id, name, camera_ids[camera_group(name)]),
            )
        connection.commit()

def write_model_from_database(database_path, output_path, intrinsics_subset):
    out = Path(output_path) / "0"
    out.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        cameras = connection.execute(
            "SELECT camera_id, model, width, height, params FROM cameras ORDER BY camera_id"
        ).fetchall()
        images = connection.execute(
            "SELECT image_id, name, camera_id FROM images ORDER BY image_id"
        ).fetchall()
    camera_lines = []
    for camera_id, model, width, height, blob in cameras:
        params = list(struct.unpack("<8d", blob))
        if intrinsics_subset:
            camera_groups = {camera_group(name) for _, name, image_camera_id in images if image_camera_id == camera_id}
            if camera_groups == {"cam2"}:
                params = [5, 6, 7, 8, 0.5, 0.6, 0.7, 0.8]
            else:
                params = [1, 2, 3, 4, 0.1, 0.2, 0.3, 0.4]
        camera_lines.append(
            f"{camera_id} OPENCV {width} {height} " + " ".join(str(value) for value in params)
        )
    (out / "cameras.txt").write_text("\\n".join(camera_lines) + "\\n")
    image_lines = []
    for image_id, name, camera_id in images:
        image_lines.append(f"{image_id} 1 0 0 0 0 0 0 {camera_id} {name}\\n")
    (out / "images.txt").write_text("\\n".join(image_lines))
    (out / "points3D.txt").write_text("1 0 0 0 255 255 255 1 1 0\\n")

if cmd == "feature_extractor":
    create_database(value("--database_path"), value("--image_path"))
elif cmd.endswith("_matcher"):
    pass
elif cmd == "matches_importer":
    pass
elif cmd in {"global_mapper", "mapper"}:
    try:
        write_model_from_database(
            value("--database_path"),
            value("--output_path"),
            "intrinsics_subset" in value("--database_path"),
        )
    except sqlite3.Error:
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
elif cmd in {"point_filtering", "bundle_adjuster", "point_triangulator"}:
    if os.environ.get("FAIL_REFINEMENT") and cmd == "point_filtering":
        raise SystemExit(7)
    inp = Path(value("--input_path"))
    out = Path(value("--output_path"))
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(inp, out)
elif cmd == "model_analyzer":
    pass
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
colour_restoration:
  mode: off
  overwrite: false
  start_sfm_immediately: true

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
    seeded = manifest["sfm"]["output_paths"]["intrinsics_database_seed"]
    assert seeded["cam1"]["params"] == [1, 2, 3, 4, 0.1, 0.2, 0.3, 0.4]
    assert seeded["cam2"]["params"] == [5, 6, 7, 8, 0.5, 0.6, 0.7, 0.8]
    cameras_txt = (run_dir / "sfm" / "selected_sparse_txt" / "cameras.txt").read_text(encoding="utf-8")
    assert "1 OPENCV 64 48 1.0 2.0 3.0 4.0 0.1 0.2 0.3 0.4" in cameras_txt
    assert "2 OPENCV 64 48 5.0 6.0 7.0 8.0 0.5 0.6 0.7 0.8" in cameras_txt
    assert Path(manifest["sfm"]["output_paths"]["undistorted_images"]).exists()
    assert (run_dir / "logs" / "colmap.log").exists()
    colmap_log = (run_dir / "logs" / "colmap.log").read_text(encoding="utf-8")
    assert "--ImageReader.single_camera_per_folder 1" in colmap_log
    assert "--ImageReader.camera_params" not in colmap_log


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
colour_restoration:
  mode: off
  overwrite: false
  start_sfm_immediately: true

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
    matching:
      mode: vocab_tree
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


def test_sfm_feature_size_flows_to_intrinsics_main_and_undistortion(
    tmp_path: Path,
    fake_tool_factory,
) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "cam1" / "a.jpg")
    write_test_jpeg(project / "raw_images" / "cam2" / "a.jpg")
    vocab = tmp_path / "vocab.bin"
    vocab.write_bytes(b"vocab")
    colmap = _fake_colmap(tmp_path / "colmap")
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
  colmap_bin: {colmap}
  lfs_bin: {fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")}
  splat_transform_bin: {fake_tool_factory("splat-transform", "splat-transform 1.0")}
  vocab_tree_path: {vocab}
advanced:
  sfm:
    feature_extraction:
      max_image_size: 2048
    undistortion:
      max_image_size: null
      follow_feature_extraction_max_image_size: true
      fallback_max_image_size: 4096
""".lstrip(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["--config", str(config), "--steps", "sfm", "--resume-policy", "overwrite"])

    assert result.exit_code == 0, result.output
    run_dir = next((project / "runs").iterdir())
    colmap_log = (run_dir / "logs" / "colmap.log").read_text(encoding="utf-8")
    assert colmap_log.count("--FeatureExtraction.max_image_size 2048") == 3
    assert "image_undistorter" in colmap_log
    assert "--max_image_size 2048" in colmap_log
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    effective = manifest["sfm"]["output_paths"]["effective_sfm_settings"]
    assert effective["feature_extraction_max_image_size"] == 2048
    assert effective["effective_undistortion_max_image_size"] == 2048


def test_sfm_full_resolution_eval_writes_second_undistortion(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "cam1" / "a.jpg")
    write_test_jpeg(project / "raw_images" / "cam2" / "a.jpg")
    vocab = tmp_path / "vocab.bin"
    vocab.write_bytes(b"vocab")
    colmap = _fake_colmap(tmp_path / "colmap")
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
  colmap_bin: {colmap}
  lfs_bin: {fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")}
  splat_transform_bin: {fake_tool_factory("splat-transform", "splat-transform 1.0")}
  vocab_tree_path: {vocab}
advanced:
  sfm:
    feature_extraction:
      max_image_size: 1024
  eval:
    enabled: true
    target_image_source: full_resolution_undistorted
""".lstrip(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["--config", str(config), "--steps", "sfm", "--resume-policy", "overwrite"])

    assert result.exit_code == 0, result.output
    run_dir = next((project / "runs").iterdir())
    colmap_log = (run_dir / "logs" / "colmap.log").read_text(encoding="utf-8")
    undistort_commands = [line for line in colmap_log.splitlines() if " image_undistorter " in line]
    assert len(undistort_commands) == 2
    assert "--max_image_size 1024" in undistort_commands[0]
    assert "undistorted_full_resolution" in undistort_commands[1]
    assert "--max_image_size" not in undistort_commands[1]
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    output_paths = manifest["sfm"]["output_paths"]
    assert output_paths["full_resolution_undistorted_images"].endswith("sfm/undistorted_full_resolution/images")


def test_sfm_sparse_refinement_feeds_undistortion(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "cam1" / "a.jpg")
    write_test_jpeg(project / "raw_images" / "cam2" / "a.jpg")
    vocab = tmp_path / "vocab.bin"
    vocab.write_bytes(b"vocab")
    colmap = _fake_colmap(tmp_path / "colmap")
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
  colmap_bin: {colmap}
  lfs_bin: {fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")}
  splat_transform_bin: {fake_tool_factory("splat-transform", "splat-transform 1.0")}
  vocab_tree_path: {vocab}
advanced:
  sfm:
    intrinsics:
      precalculate: false
    sparse_refinement:
      enabled: true
      repeats: 1
""".lstrip(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["--config", str(config), "--steps", "sfm", "--resume-policy", "overwrite"])

    assert result.exit_code == 0, result.output
    run_dir = next((project / "runs").iterdir())
    refined = run_dir / "sfm" / "refined_sparse" / "final"
    assert refined.exists()
    colmap_log = (run_dir / "logs" / "colmap.log").read_text(encoding="utf-8")
    assert "point_filtering" in colmap_log
    assert f"--input_path {refined}" in colmap_log


def test_sfm_sparse_refinement_failure_stops_by_default(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    colmap = _fake_colmap(tmp_path / "colmap")
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
  colmap_bin: {colmap}
  lfs_bin: {fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")}
  splat_transform_bin: {fake_tool_factory("splat-transform", "splat-transform 1.0")}
advanced:
  sfm:
    intrinsics:
      precalculate: false
    matching:
      mode: sequential
      sequential:
        loop_detection:
          enabled: false
    sparse_refinement:
      enabled: true
      repeats: 1
""".lstrip(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--steps", "sfm", "--resume-policy", "overwrite"],
        env={"FAIL_REFINEMENT": "1"},
    )

    assert result.exit_code != 0
    assert "COLMAP command failed during sfm.refine.iter_01.point_filtering" in result.output


def test_sfm_sparse_refinement_fallback_is_explicit(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image_0001.jpg")
    colmap = _fake_colmap(tmp_path / "colmap")
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
  colmap_bin: {colmap}
  lfs_bin: {fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")}
  splat_transform_bin: {fake_tool_factory("splat-transform", "splat-transform 1.0")}
advanced:
  sfm:
    intrinsics:
      precalculate: false
    matching:
      mode: sequential
      sequential:
        loop_detection:
          enabled: false
    sparse_refinement:
      enabled: true
      repeats: 1
      allow_fallback: true
""".lstrip(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--steps", "sfm", "--resume-policy", "overwrite"],
        env={"FAIL_REFINEMENT": "1"},
    )

    assert result.exit_code == 0, result.output
    run_dir = next((project / "runs").iterdir())
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert "Sparse refinement failed; falling back" in " ".join(manifest["sfm"]["warnings"])


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
colour_restoration:
  mode: off
  overwrite: false
  start_sfm_immediately: true

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
    matching:
      mode: {"vocab_tree" if requested_step == "sfm.match.vocab_tree" else "sequential"}
      sequential:
        loop_detection:
          enabled: false
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
colour_restoration:
  mode: off
  overwrite: false
  start_sfm_immediately: true

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
colour_restoration:
  mode: off
  overwrite: false
  start_sfm_immediately: true

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
