"""Integration tests for raw-only SfM/COLMAP undistortion with colour restoration."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from PIL import Image

from reefs.cli import app
from reefs.colour.pipeline import colour_state_path
from reefs.colour.state import ColourRestorationState, ColourStatus, load_state, save_state
from tests.conftest import write_test_jpeg


def _fake_colmap_records_undistort(path: Path, record_path: Path) -> Path:
    path.write_text(
        f"""#!/usr/bin/env python3
import shutil
import sqlite3
import sys
from pathlib import Path

args = sys.argv[1:]
if not args or args[0] in {{"-h", "--help"}}:
    print("COLMAP 4.0.4 with CUDA")
    raise SystemExit(0)
cmd = args[0]
if len(args) > 1 and args[1] in {{"-h", "--help"}}:
    print(f"help for {{cmd}}")
    raise SystemExit(0)
def value(flag):
    return args[args.index(flag) + 1]
if cmd == "feature_extractor":
    database = Path(value("--database_path"))
    image_root = Path(value("--image_path"))
    database.parent.mkdir(parents=True, exist_ok=True)
    names = [
        path.relative_to(image_root).as_posix()
        for path in sorted(image_root.rglob("*"))
        if path.suffix.lower() in {{".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}}
    ]
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE images (image_id INTEGER PRIMARY KEY, name TEXT, camera_id INTEGER)")
        connection.execute("CREATE TABLE keypoints (image_id INTEGER PRIMARY KEY, rows INTEGER)")
        connection.execute("CREATE TABLE descriptors (image_id INTEGER PRIMARY KEY, rows INTEGER)")
        connection.execute("CREATE TABLE matches (pair_id INTEGER PRIMARY KEY, rows INTEGER)")
        connection.execute("CREATE TABLE two_view_geometries (pair_id INTEGER PRIMARY KEY, rows INTEGER)")
        for image_id, name in enumerate(names, start=1):
            connection.execute("INSERT INTO images VALUES (?, ?, ?)", (image_id, name, 1))
            connection.execute("INSERT INTO keypoints VALUES (?, ?)", (image_id, 0))
            connection.execute("INSERT INTO descriptors VALUES (?, ?)", (image_id, 0))
        connection.commit()
elif cmd.endswith("_matcher"):
    pass
elif cmd in {{"global_mapper", "mapper"}}:
    out = Path(value("--output_path")) / "0"
    out.mkdir(parents=True, exist_ok=True)
    (out / "cameras.txt").write_text("1 OPENCV 64 48 1 1 1 1 0 0 0 0\\n")
    (out / "images.txt").write_text("1 1 0 0 0 0 0 0 1 image.jpg\\n0.0 0.0 1\\n")
    (out / "points3D.txt").write_text("1 0 0 0 255 255 255 1 1 0\\n")
elif cmd == "model_converter":
    inp = Path(value("--input_path"))
    out = Path(value("--output_path"))
    out.mkdir(parents=True, exist_ok=True)
    for name in ["cameras.txt", "images.txt", "points3D.txt"]:
        shutil.copy2(inp / name, out / name)
elif cmd in {"point_filtering", "point_triangulator"}:
    inp = Path(value("--input_path"))
    out = Path(value("--output_path"))
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(inp, out)
elif cmd == "model_analyzer":
    pass
elif cmd == "image_undistorter":
    Path({str(record_path)!r}).write_text(value("--image_path"))
    out = Path(value("--output_path"))
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "sparse").mkdir(parents=True, exist_ok=True)
    (out / "sparse" / "cameras.txt").write_text("1 OPENCV 64 48 1 1 1 1 0 0 0 0\\n")
else:
    raise SystemExit(2)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_completed_manual_colour_keeps_undistortion_on_raw_images(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image.jpg")
    write_test_jpeg(project / "recoloured_images" / "image.jpg")
    vocab = tmp_path / "vocab.bin"
    vocab.write_bytes(b"vocab")
    record = tmp_path / "undistort_image_path.txt"
    colmap = _fake_colmap_records_undistort(tmp_path / "colmap", record)
    run_dir = project / "runs" / "colour-complete"
    run_dir.mkdir(parents=True)
    save_state(
        colour_state_path(run_dir),
        ColourRestorationState(
            run_id="colour-complete",
            source_raw_root=project / "raw_images",
            output_recoloured_root=project / "recoloured_images",
            restoration_mode="manual",
            status=ColourStatus.COMPLETE,
        ),
    )
    config = tmp_path / "config.yml"
    config.write_text(
        f"""
colour_restoration:
  mode: manual
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
      selection_start_index: 0
      selection_end_index: 1
""".lstrip(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "colour-complete",
            "--steps",
            "sfm",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    assert record.read_text(encoding="utf-8") == str(project / "raw_images")
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["sfm"]["output_paths"]["sparse_image_source"] == "raw"
    assert manifest["sfm"]["output_paths"]["undistortion_image_source"] == "raw"


def test_off_mode_keeps_undistortion_on_raw_images(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    raw = project / "raw_images"
    raw.mkdir(parents=True)
    Image.new("RGB", (64, 48), color=(10, 20, 30)).save(raw / "image.jpg")
    vocab = tmp_path / "vocab.bin"
    vocab.write_bytes(b"vocab")
    record = tmp_path / "off_undistort_image_path.txt"
    colmap = _fake_colmap_records_undistort(tmp_path / "colmap-off", record)
    run_dir = project / "runs" / "off-run"
    run_dir.mkdir(parents=True)
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
      selection_start_index: 0
      selection_end_index: 1
""".lstrip(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "off-run",
            "--steps",
            "sfm",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    assert record.read_text(encoding="utf-8") == str(raw)
    assert not colour_state_path(run_dir).exists()
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["sfm"]["output_paths"]["undistortion_image_source"] == "raw"


def test_gray_world_keeps_undistortion_on_raw_images(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    raw = project / "raw_images"
    raw.mkdir(parents=True)
    Image.new("RGB", (64, 48), color=(10, 20, 30)).save(raw / "image.jpg")
    vocab = tmp_path / "vocab.bin"
    vocab.write_bytes(b"vocab")
    record = tmp_path / "gray_undistort_image_path.txt"
    colmap = _fake_colmap_records_undistort(tmp_path / "colmap-gray", record)
    run_dir = project / "runs" / "gray-run"
    run_dir.mkdir(parents=True)
    config = tmp_path / "config.yml"
    config.write_text(
        f"""
colour_restoration:
  mode: gray_world
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
      selection_start_index: 0
      selection_end_index: 1
""".lstrip(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "gray-run",
            "--steps",
            "sfm",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    assert record.read_text(encoding="utf-8") == str(raw)
    assert not (project / "recoloured_images").exists()
    assert not colour_state_path(run_dir).exists()
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["sfm"]["output_paths"]["undistortion_image_source"] == "raw"


def test_previous_run_recoloured_images_are_not_adopted_for_new_sfm_run(
    tmp_path: Path, fake_tool_factory, monkeypatch
) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image.jpg")
    write_test_jpeg(project / "recoloured_images" / "image.jpg")
    vocab = tmp_path / "vocab.bin"
    vocab.write_bytes(b"vocab")
    record = tmp_path / "adopted_undistort_image_path.txt"
    colmap = _fake_colmap_records_undistort(tmp_path / "colmap-adopt", record)
    run_dir = project / "runs" / "colour-adopt"
    run_dir.mkdir(parents=True)
    config = tmp_path / "config.yml"
    config.write_text(
        f"""
colour_restoration:
  mode: manual
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
      selection_start_index: 0
      selection_end_index: 1
""".lstrip(),
        encoding="utf-8",
    )

    def continue_without_waiting(**_: object):
        return {}, None

    monkeypatch.setattr("reefs.cli._start_colour_gui_for_pipeline", continue_without_waiting)

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "colour-adopt",
            "--steps",
            "sfm",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Found existing complete same-run recoloured_images/" not in result.output
    assert record.read_text(encoding="utf-8") == str(project / "raw_images")
    state = load_state(colour_state_path(run_dir))
    assert state.status == ColourStatus.INCOMPLETE
    assert state.output_recoloured_root == project / "recoloured_images"
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["colour_restoration"]["status"] == "incomplete"
    assert manifest["colour_restoration"]["adopted_existing_recoloured_images"] is False
    assert manifest["sfm"]["output_paths"]["undistortion_image_source"] == "raw"


def test_previous_run_recoloured_images_are_not_reused_by_foundation_only_run(
    tmp_path: Path, fake_tool_factory, monkeypatch
) -> None:
    project = tmp_path / "project"
    raw = project / "raw_images"
    recoloured = project / "recoloured_images"
    raw.mkdir(parents=True)
    recoloured.mkdir(parents=True)
    run_dir = project / "runs" / "colour-adopt-new-config"
    run_dir.mkdir(parents=True)
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(raw / "image.jpg")
    Image.new("RGB", (8, 6), color=(30, 20, 10)).save(recoloured / "image.jpg")
    config = tmp_path / "config.yml"
    config.write_text(
        f"""
colour_restoration:
  mode: manual
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
    feature_extraction:
      max_num_features: 1234
""".lstrip(),
        encoding="utf-8",
    )

    def continue_without_waiting(**_: object):
        return {}, None

    monkeypatch.setattr("reefs.cli._start_colour_gui_for_pipeline", continue_without_waiting)

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "colour-adopt-new-config",
            "--steps",
            "foundation",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Found existing complete same-run recoloured_images/" not in result.output
    state = load_state(colour_state_path(run_dir))
    assert state.status == ColourStatus.INCOMPLETE
    assert "adopted_existing_recoloured_images" not in state.relevant_config


def test_incomplete_manual_colour_state_still_keeps_sfm_undistortion_raw(
    tmp_path: Path,
    fake_tool_factory,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image.jpg")
    vocab = tmp_path / "vocab.bin"
    vocab.write_bytes(b"vocab")
    record = tmp_path / "undistort_incomplete_image_path.txt"
    colmap = _fake_colmap_records_undistort(tmp_path / "colmap-incomplete", record)
    run_dir = project / "runs" / "colour-incomplete"
    run_dir.mkdir(parents=True)
    save_state(
        colour_state_path(run_dir),
        ColourRestorationState(
            run_id="colour-incomplete",
            source_raw_root=project / "raw_images",
            output_recoloured_root=project / "recoloured_images",
            restoration_mode="manual",
            status=ColourStatus.INCOMPLETE,
        ),
    )
    config = tmp_path / "config.yml"
    config.write_text(
        f"""
colour_restoration:
  mode: manual
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
      selection_start_index: 0
      selection_end_index: 1
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.setattr("reefs.cli._start_colour_gui_for_pipeline", lambda **_: ({}, None))

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--run-id",
            "colour-incomplete",
            "--steps",
            "sfm",
            "--resume-policy",
            "overwrite",
        ],
    )

    assert result.exit_code == 0, result.output
    assert record.read_text(encoding="utf-8") == str(project / "raw_images")
