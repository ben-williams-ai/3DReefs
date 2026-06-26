"""Live terminal reporting for long pipeline runs."""

from __future__ import annotations

import sys
from typing import TextIO

from reefs.logging.run_logger import RunLogger


class TerminalReporter:
    """Mirror important pipeline events to stdout and the run log."""

    def __init__(self, *, logger: RunLogger | None = None, stream: TextIO | None = None) -> None:
        self.logger = logger
        self.stream = stream or sys.stdout

    def info(self, message: str) -> None:
        """Print and persist an informational message."""
        print(message, file=self.stream, flush=True)
        if self.logger:
            self.logger.info(message)

    def warning(self, message: str) -> None:
        """Print and persist a warning message."""
        print(message, file=self.stream, flush=True)
        if self.logger:
            self.logger.warning(message)

    def stage_started(self, stage: str) -> None:
        """Report that a stage started."""
        self.info(f"[{stage}] started")

    def stage_completed(self, stage: str, elapsed_seconds: float | None = None) -> None:
        """Report that a stage completed."""
        suffix = f" in {elapsed_seconds:.2f}s" if elapsed_seconds is not None else ""
        self.info(f"[{stage}] complete{suffix}")

    def stage_failed(self, stage: str, error: str) -> None:
        """Report that a stage failed."""
        self.warning(f"[{stage}] failed: {error}")

    def stage_interrupted(self, stage: str, error: str) -> None:
        """Report that a stage was interrupted."""
        self.warning(f"[{stage}] interrupted: {error}")
