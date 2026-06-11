"""Timing records for pipeline stages."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Callable, Iterator


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(UTC).isoformat()


@dataclass
class TimingRecorder:
    """Collect stage timing records."""

    stages: list[dict[str, object]] = field(default_factory=list)
    on_update: Callable[[], None] | None = None

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """Record elapsed wall-clock time for a stage."""
        started_at = utc_now()
        start = perf_counter()
        status = "passed"
        try:
            yield
        except Exception:
            status = "failed"
            raise
        finally:
            ended_at = utc_now()
            self.stages.append(
                {
                    "name": name,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "duration_seconds": round(perf_counter() - start, 6),
                    "status": status,
                }
            )
            if self.on_update:
                self.on_update()

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable timing record."""
        return {"stages": self.stages}
