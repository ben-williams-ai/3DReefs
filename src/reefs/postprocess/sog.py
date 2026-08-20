"""Final SOG export for a merged site splat."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from reefs.config.models import SogConfig
from reefs.logging.timings import utc_now


@dataclass(frozen=True)
class SogStatus:
    """Final SOG export status."""

    status: str
    source_merged_ply: Path
    output_sog: Path
    tool_version: str | None
    command_summary: list[str]
    duration_seconds: float | None
    failure_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable SOG status."""
        return {
            "status": self.status,
            "source_merged_ply": str(self.source_merged_ply),
            "output_sog": str(self.output_sog),
            "tool_version": self.tool_version,
            "command_summary": self.command_summary,
            "duration_seconds": self.duration_seconds,
            "failure_reason": self.failure_reason,
        }


def build_sog_command(binary: str, source_file: Path, output_file: Path, config: SogConfig) -> list[str]:
    """Build the splat-transform command for final SOG export."""
    command = [binary, "-w"]
    if config.iterations is not None:
        command.extend(["--iterations", str(config.iterations)])
    command.append(str(source_file))
    if config.filter_nan:
        command.append("--filter-nan")
    if config.filter_harmonics is not None:
        command.extend(["--filter-harmonics", str(config.filter_harmonics)])
    command.append(str(output_file))
    return command


def _append_log(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        if not line.endswith("\n"):
            handle.write("\n")


def run_sog_export(
    *,
    splat_transform_bin: str,
    source_file: Path,
    output_file: Path,
    config: SogConfig,
    log_path: Path,
    tool_version: str | None = None,
) -> SogStatus:
    """Run final SOG export and return structured status."""
    if not source_file.exists():
        return SogStatus(
            status="failed",
            source_merged_ply=source_file,
            output_sog=output_file,
            tool_version=tool_version,
            command_summary=[],
            duration_seconds=None,
            failure_reason="merged_cleaned_ply_missing",
        )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    command = build_sog_command(splat_transform_bin, source_file, output_file, config)
    start = perf_counter()
    started_at = utc_now()
    _append_log(log_path, f"\n## splat.sog | {started_at}\n$ {' '.join(command)}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert process.stdout is not None
    for line in process.stdout:
        _append_log(log_path, line.rstrip("\n"))
    return_code = process.wait()
    duration = round(perf_counter() - start, 6)
    _append_log(log_path, f"[exit_code] {return_code}\n[duration_seconds] {duration}")
    status = "complete" if return_code == 0 and output_file.exists() else "failed"
    return SogStatus(
        status=status,
        source_merged_ply=source_file,
        output_sog=output_file,
        tool_version=tool_version,
        command_summary=command,
        duration_seconds=duration,
        failure_reason=None if status == "complete" else f"splat-transform sog failed: exit {return_code}",
    )
