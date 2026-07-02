"""Bounded COLMAP subprocess runner with stage logging."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from reefs.colmap.commands import ColmapCommand
from reefs.logging.timings import utc_now


@dataclass(frozen=True)
class CommandResult:
    """Result from a COLMAP command."""

    stage: str
    args: list[str]
    returncode: int
    started_at: str
    ended_at: str
    duration_seconds: float

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable command result."""
        return {
            "stage": self.stage,
            "args": self.args,
            "returncode": self.returncode,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": self.duration_seconds,
        }


class ColmapCommandError(RuntimeError):
    """Raised when a COLMAP command fails."""


def append_log(log_path: Path, text: str) -> None:
    """Append text to a command log."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")


def run_colmap_command(command: ColmapCommand, *, log_path: Path, cwd: Path | None = None) -> CommandResult:
    """Run one COLMAP command and append stdout/stderr to the COLMAP log."""
    started_at = utc_now()
    start = perf_counter()
    append_log(log_path, f"\n## {command.stage} | {started_at}\n$ {' '.join(command.args)}\n")
    process = subprocess.Popen(
        command.args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert process.stdout is not None
    append_log(log_path, "\n[output]")
    missing_pair_images = False
    for line in process.stdout:
        text = line.rstrip("\n")
        if command.stage == "sfm.match.cross_camera_pairs" and " does not exist." in text:
            missing_pair_images = True
        append_log(log_path, text)
    returncode = process.wait()
    ended_at = utc_now()
    duration = round(perf_counter() - start, 6)
    append_log(log_path, f"\n[exit_code] {returncode}\n[duration_seconds] {duration}\n")
    result = CommandResult(
        stage=command.stage,
        args=command.args,
        returncode=returncode,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration,
    )
    if returncode != 0:
        raise ColmapCommandError(f"COLMAP command failed during {command.stage}: exit {returncode}")
    if missing_pair_images:
        raise ColmapCommandError(
            "COLMAP command failed during sfm.match.cross_camera_pairs: pair list references missing images"
        )
    return result
