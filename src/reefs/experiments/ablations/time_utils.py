"""Small time helpers for ablation records."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(UTC).isoformat()
