"""Run status record helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from reefs.logging.timings import utc_now


@dataclass
class RunStatus:
    """Mutable status for a foundation run."""

    status: str = "created"
    current_stage: str = "created"
    last_completed_stage: str | None = None
    started_at: str = field(default_factory=utc_now)
    ended_at: str | None = None
    warnings_count: int = 0
    errors: list[str] = field(default_factory=list)

    def mark_stage(self, stage: str) -> None:
        """Set the current stage."""
        self.current_stage = stage

    def complete_stage(self, stage: str) -> None:
        """Record a completed stage."""
        self.last_completed_stage = stage

    def finish(self, status: str = "complete") -> None:
        """Finish the run with the given status."""
        self.status = status
        self.current_stage = status
        self.ended_at = utc_now()

    def fail(self, error: str) -> None:
        """Finish the run as failed."""
        self.errors.append(error)
        self.finish("preflight_failed")

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable status record."""
        return {
            "status": self.status,
            "current_stage": self.current_stage,
            "last_completed_stage": self.last_completed_stage,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "warnings_count": self.warnings_count,
            "errors": self.errors,
        }
