"""Tests for external tool validation."""

from __future__ import annotations

import subprocess

from reefs.preflight import tools


def _completed(output: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["tool"], returncode=returncode, stdout=output, stderr="")


def test_colmap_validation_passes(monkeypatch) -> None:
    monkeypatch.setattr(tools.shutil, "which", lambda _: "/bin/tool")
    monkeypatch.setattr(tools, "run_tool_command", lambda *_args, **_kwargs: _completed("COLMAP 4.0.4"))

    result = tools.validate_tool(tool_name="COLMAP", binary="colmap", target_version="4.0.4")

    assert result.status == "passed"


def test_colmap_validation_can_read_version_from_help(monkeypatch) -> None:
    monkeypatch.setattr(tools.shutil, "which", lambda _: "/bin/tool")
    calls: list[tuple[str, ...]] = []

    def fake_run_tool_command(_binary: str, args: list[str]):
        calls.append(tuple(args))
        if args == ["-h"]:
            return _completed("COLMAP 4.0.4 -- Structure-from-Motion and Multi-View Stereo")
        return _completed("help")

    monkeypatch.setattr(tools, "run_tool_command", fake_run_tool_command)

    result = tools.validate_tool(
        tool_name="COLMAP",
        binary="colmap",
        target_version="4.0.4",
        version_args=["-h"],
    )

    assert result.status == "passed"
    assert calls[0] == ("-h",)


def test_lfs_validation_fails_wrong_version(monkeypatch) -> None:
    monkeypatch.setattr(tools.shutil, "which", lambda _: "/bin/tool")
    monkeypatch.setattr(tools, "run_tool_command", lambda *_args, **_kwargs: _completed("v0.5.1"))

    result = tools.validate_tool(
        tool_name="LichtFeld Studio", binary="lfs", target_version="v0.5.2"
    )

    assert result.status == "failed"
    assert "target v0.5.2" in result.message


def test_sog_validation_checks_availability(monkeypatch) -> None:
    monkeypatch.setattr(tools.shutil, "which", lambda _: None)

    result = tools.validate_tool(
        tool_name="SOG conversion", binary="splat-transform", target_version=None
    )

    assert result.status == "failed"
    assert "not found" in result.message
