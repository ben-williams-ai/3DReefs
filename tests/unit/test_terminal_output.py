"""Tests for live terminal reporting helpers."""

from __future__ import annotations

from pathlib import Path

from reefs.logging.run_logger import RunLogger
from reefs.logging.terminal import TerminalReporter


def test_terminal_reporter_prints_stage_messages_and_logs(tmp_path: Path, capsys) -> None:
    logger = RunLogger(tmp_path / "pipeline.log", tmp_path / "warnings.log")
    reporter = TerminalReporter(logger=logger)

    reporter.stage_started("splat.patch")
    reporter.stage_completed("splat.patch", 1.234)
    reporter.stage_failed("splat.train", "boom")
    reporter.stage_interrupted("splat.merge", "stopped")

    output = capsys.readouterr().out
    assert "[splat.patch] started" in output
    assert "[splat.patch] complete in 1.23s" in output
    assert "[splat.train] failed: boom" in output
    assert "[splat.merge] interrupted: stopped" in output
    log = (tmp_path / "pipeline.log").read_text(encoding="utf-8")
    assert "[splat.patch] started" in log
    assert "[splat.patch] complete in 1.23s" in log
    assert "[splat.train] failed: boom" in log
    assert "[splat.merge] interrupted: stopped" in log


def test_terminal_reporter_tees_tool_output(capsys) -> None:
    reporter = TerminalReporter()

    reporter.tee_line("hello from tool")

    assert "hello from tool" in capsys.readouterr().out
