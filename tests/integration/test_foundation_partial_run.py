"""Integration tests for partial-run resume safety."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from reefs.io.yaml_json import write_json, write_yaml
from tests.conftest import write_config


def _prepare_project(tmp_path: Path, fake_tool_factory):
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
    return project, config


def test_non_interactive_partial_run_requires_policy(tmp_path: Path, fake_tool_factory) -> None:
    project, config = _prepare_project(tmp_path, fake_tool_factory)
    previous = project / "runs" / "old"
    previous.mkdir(parents=True)
    write_json(previous / "run_status.json", {"status": "preflight_failed"})
    write_json(previous / "run_manifest.json", {"requested_steps": ["sfm"]})
    write_yaml(previous / "effective_config.yml", {"project": {"dir": str(project)}})

    result = CliRunner().invoke(app, ["--config", str(config), "--steps", "sfm"])

    assert result.exit_code != 0
    assert "non-interactive run" in result.output


def test_resume_policy_records_each_requested_step(tmp_path: Path, fake_tool_factory) -> None:
    project, config = _prepare_project(tmp_path, fake_tool_factory)
    previous = project / "runs" / "old"
    previous.mkdir(parents=True)
    write_json(previous / "run_status.json", {"status": "preflight_failed"})
    write_json(previous / "run_manifest.json", {"requested_steps": ["sfm", "splat"]})
    write_yaml(previous / "effective_config.yml", {"project": {"dir": str(project)}})

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config),
            "--steps",
            "sfm,splat",
            "--resume-policy",
            "resume",
        ],
    )

    assert result.exit_code == 0, result.output
    new_runs = [p for p in (project / "runs").iterdir() if p.name != "old"]
    manifest = json.loads((new_runs[0] / "run_manifest.json").read_text(encoding="utf-8"))
    assert [event["step"] for event in manifest["resume_events"]] == ["sfm", "splat"]
    assert {event["decision"] for event in manifest["resume_events"]} == {"continue"}
