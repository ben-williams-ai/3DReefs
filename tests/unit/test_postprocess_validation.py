"""Tests for post-processing validation and resume helpers."""

from __future__ import annotations

import subprocess
import sys
import types
from types import SimpleNamespace
from pathlib import Path

import pytest

from reefs.config.models import ResumePolicy
from reefs.postprocess.cleanup import validate_cleanup_backend
from reefs.postprocess.resume import (
    discover_existing_postprocess_outputs,
    inspect_postprocess_config_changes,
    resolve_postprocess_outputs,
)
from reefs.preflight import tools
from reefs.splat.validation import create_splat_paths
from tests.conftest import write_config


def _completed(output: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["tool"], returncode=returncode, stdout=output, stderr="")


def test_validate_wildflow_checks_cleanup_and_merge_callables(monkeypatch) -> None:
    wildflow = types.ModuleType("wildflow")
    splat = types.ModuleType("wildflow.splat")
    splat.cleanup_splats = lambda _params: None
    splat.merge_ply_files = lambda _params: None
    wildflow.splat = splat
    monkeypatch.setitem(sys.modules, "wildflow", wildflow)
    monkeypatch.setitem(sys.modules, "wildflow.splat", splat)

    result = validate_cleanup_backend(SimpleNamespace(enabled=True))

    assert result.status == "passed"


def test_validate_wildflow_fails_missing_merge_callable(monkeypatch) -> None:
    wildflow = types.ModuleType("wildflow")
    splat = types.ModuleType("wildflow.splat")
    splat.cleanup_splats = lambda _params: None
    wildflow.splat = splat
    monkeypatch.setitem(sys.modules, "wildflow", wildflow)
    monkeypatch.setitem(sys.modules, "wildflow.splat", splat)

    result = validate_cleanup_backend(SimpleNamespace(enabled=True))

    assert result.status == "failed"
    assert "merge_ply_files" in result.message


def test_validate_splat_transform_checks_required_formats(monkeypatch) -> None:
    monkeypatch.setattr(tools.shutil, "which", lambda _: "/bin/tool")
    monkeypatch.setattr(
        tools,
        "run_tool_command",
        lambda _binary, args: _completed("splat-transform v1.10.2" if args == ["--version"] else ".ply .sog --overwrite"),
    )

    result = tools.validate_splat_transform("splat-transform", require_sog=True)

    assert result.status == "passed"


def test_validate_splat_transform_fails_missing_sog(monkeypatch) -> None:
    monkeypatch.setattr(tools.shutil, "which", lambda _: "/bin/tool")
    monkeypatch.setattr(
        tools,
        "run_tool_command",
        lambda _binary, args: _completed("splat-transform v1.10.2" if args == ["--version"] else ".ply --overwrite"),
    )

    result = tools.validate_splat_transform("splat-transform", require_sog=True)

    assert result.status == "failed"
    assert ".sog" in result.message


def test_discover_existing_postprocess_outputs(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    paths = create_splat_paths(SimpleNamespace(run_dir=run_dir, logs_dir=run_dir / "logs"))
    cleaned = paths.patches / "p000" / "splat" / "splat_finished_clean.ply"
    cleaned.parent.mkdir(parents=True)
    cleaned.write_text("ply\n", encoding="utf-8")
    paths.merged.mkdir(parents=True)
    paths.merged_ply.write_text("ply\n", encoding="utf-8")
    paths.sog.mkdir(parents=True)
    paths.final_sog.write_text("sog\n", encoding="utf-8")

    outputs = discover_existing_postprocess_outputs(
        paths=paths,
        requested_steps=["splat.postprocess"],
    )

    assert [output.stage for output in outputs] == ["splat.cleanup", "splat.merge", "splat.sog"]


def test_resolve_postprocess_outputs_fail_policy(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    paths = create_splat_paths(SimpleNamespace(run_dir=run_dir, logs_dir=run_dir / "logs"))
    paths.final_sog.parent.mkdir(parents=True)
    paths.final_sog.write_text("sog\n", encoding="utf-8")
    outputs = discover_existing_postprocess_outputs(paths=paths, requested_steps=["splat.sog"])

    with pytest.raises(ValueError, match="Existing post-processing outputs"):
        resolve_postprocess_outputs(existing_outputs=outputs, resume_policy=ResumePolicy.FAIL)


def test_inspect_postprocess_config_changes(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    config_path = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=fake_tool_factory("colmap", "COLMAP 4.0.4"),
        lfs_bin=fake_tool_factory("lfs", "LichtFeld Studio v0.5.2"),
        splat_transform_bin=fake_tool_factory("splat-transform", "splat-transform 1.0"),
    )
    from reefs.config.loader import load_config
    from reefs.io.yaml_json import write_json

    config = load_config(config_path)
    paths = create_splat_paths(
        SimpleNamespace(run_dir=project / "runs" / "old", logs_dir=project / "runs" / "old" / "logs")
    )
    write_json(paths.postprocess_manifest, {"effective_settings": {"cleanup": {"radius": 999}}})

    changes = inspect_postprocess_config_changes(paths, config)

    assert changes
