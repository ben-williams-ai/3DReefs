"""Human-readable run logging helpers."""

from __future__ import annotations

from pathlib import Path

from reefs.logging.timings import utc_now


class RunLogger:
    """Append-safe logger for pipeline and warning messages."""

    def __init__(self, pipeline_log: Path, warnings_log: Path) -> None:
        self.pipeline_log = pipeline_log
        self.warnings_log = warnings_log
        self.pipeline_log.parent.mkdir(parents=True, exist_ok=True)
        self.pipeline_log.touch(exist_ok=True)

    def info(self, message: str) -> None:
        """Append an informational message."""
        self._append(self.pipeline_log, "INFO", message)

    def warning(self, message: str) -> None:
        """Append a warning message to both logs."""
        self._append(self.pipeline_log, "WARNING", message)
        self._append(self.warnings_log, "WARNING", message)

    @staticmethod
    def _append(path: Path, level: str, message: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{utc_now()} [{level}] {message}\n")
