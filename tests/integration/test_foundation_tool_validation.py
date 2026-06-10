"""Integration tests for bounded tool validation."""

from __future__ import annotations

import subprocess
from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from reefs.preflight import tools
from tests.conftest import write_config


def test_foundation_invokes_only_version_and_help_commands(
    tmp_path: Path, fake_tool_factory, monkeypatch
) -> None:
    project = tmp_path / "project"
    (project / "raw_images").mkdir(parents=True)
    (project / "raw_images" / "image_0001.jpg").write_text("", encoding="utf-8")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
    )
    calls: list[list[str]] = []

    def fake_run_tool_command(binary: str, args: list[str], timeout: float = 5.0):
        calls.append([binary, *args])
        output = "COLMAP 4.0.4 LichtFeld Studio v0.5.2 splat-transform"
        return subprocess.CompletedProcess(args=[binary, *args], returncode=0, stdout=output, stderr="")

    monkeypatch.setattr(tools, "run_tool_command", fake_run_tool_command)

    result = CliRunner().invoke(app, ["--config", str(config)])

    assert result.exit_code == 0, result.output
    assert calls
    assert all(call[1] in {"--version", "--help", "-h"} for call in calls)
