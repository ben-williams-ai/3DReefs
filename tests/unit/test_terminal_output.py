"""Tests for live terminal reporting helpers."""

from __future__ import annotations

from pathlib import Path

from reefs.logging.run_logger import RunLogger
from reefs.logging.terminal import TerminalReporter
from reefs.logging.timings import TimingRecorder
from reefs.runs.manifest import RunPaths
from reefs.runs.recorder import RunRecorder
from reefs.runs.status import RunStatus


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


def test_run_recorder_reports_stage_lifecycle(tmp_path: Path, capsys) -> None:
    paths = RunPaths(
        run_id="terminal_test",
        run_dir=tmp_path / "terminal_test",
        effective_config=tmp_path / "terminal_test" / "effective_config.yml",
        cli_overrides=tmp_path / "terminal_test" / "cli_overrides.json",
        manifest=tmp_path / "terminal_test" / "run_manifest.json",
        status=tmp_path / "terminal_test" / "run_status.json",
        timings=tmp_path / "terminal_test" / "timings.json",
        logs_dir=tmp_path / "terminal_test" / "logs",
        pipeline_log=tmp_path / "terminal_test" / "logs" / "pipeline.log",
        warnings_log=tmp_path / "terminal_test" / "logs" / "warnings.log",
    )
    paths.run_dir.mkdir()
    recorder = RunRecorder(
        run_paths=paths,
        effective_config_data={},
        cli_overrides_record={},
        manifest={},
        status=RunStatus(),
        timings=TimingRecorder(),
        reporter=TerminalReporter(),
    )

    recorder.stage_started("sfm.match")
    recorder.stage_completed("sfm.match")

    output = capsys.readouterr().out
    assert "[sfm.match] started" in output
    assert "[sfm.match] complete" in output
