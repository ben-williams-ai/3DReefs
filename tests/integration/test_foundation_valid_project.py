"""Integration test for a valid foundation run."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from tests.conftest import write_config


def test_valid_foundation_run_creates_required_records(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    raw = project / "raw_images"
    raw.mkdir(parents=True)
    (raw / "image_0001.jpg").write_text("", encoding="utf-8")
    colmap = fake_tool_factory("colmap", "COLMAP 4.0.4")
    lfs = fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")
    sog = fake_tool_factory("splat-transform", "splat-transform 1.0")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=colmap,
        lfs_bin=lfs,
        splat_transform_bin=sog,
    )

    result = CliRunner().invoke(app, ["--config", str(config)])

    assert result.exit_code == 0, result.output
    run_dirs = list((project / "runs").iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    for relative in [
        "effective_config.yml",
        "cli_overrides.json",
        "run_manifest.json",
        "run_status.json",
        "timings.json",
        "logs/pipeline.log",
    ]:
        assert (run_dir / relative).exists()
    assert not (run_dir / "logs" / "warnings.log").exists()
    assert not (run_dir / "reports").exists()
    status = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))
    assert status["status"] == "complete"
    timings = json.loads((run_dir / "timings.json").read_text(encoding="utf-8"))
    assert "write_run_records" in {stage["name"] for stage in timings["stages"]}
