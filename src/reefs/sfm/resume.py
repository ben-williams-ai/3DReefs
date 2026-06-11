"""SfM resume/status helpers."""

from __future__ import annotations


def sfm_step_overlaps(step: str, previous_steps: list[str]) -> bool:
    """Return whether a requested SfM step overlaps previous requested steps."""
    if step == "sfm":
        return any(previous == "sfm" or previous.startswith("sfm.") for previous in previous_steps)
    return step in previous_steps or "sfm" in previous_steps
