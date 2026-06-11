"""Integration test for recoloured image use during undistortion."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from tests.conftest import write_test_jpeg


def _fake_colmap_records_undistort(path: Path, record_path: Path) -> Path:
    path.write_text(
        f"""#!/usr/bin/env python3
import shutil
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
    Path(value("--database_path")).parent.mkdir(parents=True, exist_ok=True)
    Path(value("--database_path")).write_bytes(b"sqlite")
elif cmd.endswith("_matcher"):
    pass
elif cmd in {{"global_mapper", "mapper"}}:
    out = Path(value("--output_path")) / "0"
    out.mkdir(parents=True, exist_ok=True)
    (out / "cameras.txt").write_text("1 OPENCV 64 48 1 1 1 1 0 0 0 0\\n")
    (out / "images.txt").write_text("1 1 0 0 0 0 0 0 1 image.jpg\\n\\n")
    (out / "points3D.txt").write_text("1 0 0 0 255 255 255 1 1 0\\n")
elif cmd == "model_converter":
    inp = Path(value("--input_path"))
    out = Path(value("--output_path"))
    out.mkdir(parents=True, exist_ok=True)
    for name in ["cameras.txt", "images.txt", "points3D.txt"]:
        shutil.copy2(inp / name, out / name)
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


def test_recoloured_images_are_used_only_for_undistortion(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "image.jpg")
    write_test_jpeg(project / "recoloured_images" / "image.jpg")
    vocab = tmp_path / "vocab.bin"
    vocab.write_bytes(b"vocab")
    record = tmp_path / "undistort_image_path.txt"
    colmap = _fake_colmap_records_undistort(tmp_path / "colmap", record)
    config = tmp_path / "config.yml"
    config.write_text(
        f"""
project:
  dir: {project}
  recolour_images: true
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

    result = CliRunner().invoke(app, ["--config", str(config), "--steps", "sfm", "--resume-policy", "overwrite"])

    assert result.exit_code == 0, result.output
    assert record.read_text(encoding="utf-8") == str(project / "recoloured_images")
    run_dir = next((project / "runs").iterdir())
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["sfm"]["output_paths"]["sparse_image_source"] == "raw"
    assert manifest["sfm"]["output_paths"]["undistortion_image_source"] == "recoloured"
