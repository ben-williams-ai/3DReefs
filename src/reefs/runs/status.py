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
    updated_at: str = field(default_factory=utc_now)
    ended_at: str | None = None
    warnings_count: int = 0
    errors: list[str] = field(default_factory=list)
    stage_statuses: dict[str, str] = field(default_factory=dict)
    active_command: dict[str, object] | None = None

    def mark_stage(self, stage: str) -> None:
        """Set the current stage."""
        self.status = "running"
        self.current_stage = stage
        self.stage_statuses[stage] = "running"
        self.updated_at = utc_now()

    def complete_stage(self, stage: str) -> None:
        """Record a completed stage."""
        self.last_completed_stage = stage
        self.current_stage = stage
        self.stage_statuses[stage] = "complete"
        self.active_command = None
        self.updated_at = utc_now()

    def skip_stage(self, stage: str, reason: str = "skipped") -> None:
        """Record a skipped stage."""
        self.stage_statuses[stage] = reason
        self.updated_at = utc_now()

    def mark_active_command(self, *, stage: str, args: list[str]) -> None:
        """Record the external command currently running."""
        self.active_command = {"stage": stage, "args": args, "started_at": utc_now()}
        self.updated_at = utc_now()

    def finish(self, status: str = "complete") -> None:
        """Finish the run with the given status."""
        self.status = status
        self.current_stage = status
        self.ended_at = utc_now()
        self.updated_at = self.ended_at

    def fail(self, error: str, status: str = "failed") -> None:
        """Finish the run as failed."""
        self.errors.append(error)
        if self.current_stage not in {"created", "complete", "failed", "interrupted"}:
            self.stage_statuses[self.current_stage] = "failed"
        self.finish(status)

    def interrupt(self, error: str) -> None:
        """Finish the run as interrupted."""
        self.errors.append(error)
        if self.current_stage not in {"created", "complete", "failed", "interrupted"}:
            self.stage_statuses[self.current_stage] = "interrupted"
        self.finish("interrupted")

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable status record."""
        return {
            "status": self.status,
            "current_stage": self.current_stage,
            "last_completed_stage": self.last_completed_stage,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "ended_at": self.ended_at,
            "warnings_count": self.warnings_count,
            "errors": self.errors,
            "stage_statuses": self.stage_statuses,
            "active_command": self.active_command,
        }
