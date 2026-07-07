"""Mocked failure-path tests for SfM CLI validation."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from tests.conftest import write_test_jpeg


def test_sfm_missing_vocab_tree_fails_before_colmap(tmp_path: Path, fake_tool_factory) -> None:
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
      mode: sequential_vocab_tree
""".lstrip(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["--config", str(config), "--steps", "sfm"])

    assert result.exit_code != 0
    assert "requires a valid feature-compatible vocabulary tree path" in result.output
