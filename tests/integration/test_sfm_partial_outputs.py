"""Integration tests for SfM partial-output decisions."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from reefs.io.yaml_json import write_json, write_yaml
from tests.conftest import write_test_jpeg


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
