"""Integration tests for colour/SfM resume and waiting behaviour."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from reefs.colour.pipeline import colour_state_path
from reefs.colour.state import ColourRestorationState, ColourStatus, save_state
from tests.conftest import write_test_jpeg


def _write_colour_sfm_config(
    path: Path,
    *,
    project: Path,
    colmap: Path,
    lfs: Path,
    splat_transform: Path,
    start_sfm_immediately: bool,
) -> Path:
    vocab = path.with_name("vocab.bin")
    vocab.write_bytes(b"vocab")
    path.write_text(
        f"""
colour_restoration:
  mode: manual
  overwrite: false
  start_sfm_immediately: {str(start_sfm_immediately).lower()}

project:
  dir: {project}
tools:
  colmap_bin: {colmap}
  lfs_bin: {lfs}
  splat_transform_bin: {splat_transform}
  vocab_tree_path: {vocab}
advanced:
  sfm:
    intrinsics:
      precalculate: false
      selection_start_index: 0
      selection_end_index: 1
""".lstrip(),
        encoding="utf-8",
    )
    return path


def _fake_colmap_creates_database(path: Path) -> Path:
    path.write_text(
        """#!/usr/bin/env python3
import sys
from pathlib import Path

args = sys.argv[1:]
if not args or args[0] in {"-h", "--help"}:
    print("COLMAP 4.0.4")
    raise SystemExit(0)
if args[0] == "feature_extractor":
    database = Path(args[args.index("--database_path") + 1])
    database.parent.mkdir(parents=True, exist_ok=True)
    database.write_bytes(b"sqlite")
raise SystemExit(0)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_start_sfm_immediately_false_waits_for_colour_completion(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "img1.jpg")
    run_dir = project / "runs" / "colour-run"
    run_dir.mkdir(parents=True)
    save_state(
        colour_state_path(run_dir),
        ColourRestorationState(
            run_id="colour-run",
            source_raw_root=project / "raw_images",
            output_recoloured_root=project / "recoloured_images",
            status=ColourStatus.INCOMPLETE,
        ),
    )
    config = _write_colour_sfm_config(
        tmp_path / "config.yml",
        project=project,
        colmap=_fake_colmap_creates_database(tmp_path / "colmap-wait"),
        lfs=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        start_sfm_immediately=False,
    )

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "colour-run", "--steps", "sfm.extract"],
    )

    assert result.exit_code != 0
    assert "Colour restoration is not complete" in result.output


def test_start_sfm_immediately_true_allows_raw_extract_before_colour_completion(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    write_test_jpeg(project / "raw_images" / "img1.jpg")
    run_dir = project / "runs" / "colour-run"
    run_dir.mkdir(parents=True)
    save_state(
        colour_state_path(run_dir),
        ColourRestorationState(
            run_id="colour-run",
            source_raw_root=project / "raw_images",
            output_recoloured_root=project / "recoloured_images",
            status=ColourStatus.INCOMPLETE,
        ),
    )
    config = _write_colour_sfm_config(
        tmp_path / "config.yml",
        project=project,
        colmap=_fake_colmap_creates_database(tmp_path / "colmap-run"),
        lfs=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform=fake_tool_factory("splat-transform", "splat-transform 1.0"),
        start_sfm_immediately=True,
    )

    result = CliRunner().invoke(
        app,
        ["--config", str(config), "--run-id", "colour-run", "--steps", "sfm.extract"],
    )

    assert result.exit_code == 0, result.output
    assert (run_dir / "sfm" / "database.db").exists()
