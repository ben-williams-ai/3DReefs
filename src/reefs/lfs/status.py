"""LichtFeld Studio progress parsing and status classification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PROGRESS_RE = re.compile(r"(\d+)/(\d+)\s*\|\s*Loss:\s*([0-9.eE+-]+)\s*\|\s*Splats:\s*(\d+)")


@dataclass(frozen=True)
class LfsProgress:
    """One parsed LFS progress line."""

    completed_iterations: int
    requested_iterations: int
    loss: float
    splats: int


def parse_lfs_progress_lines(lines: list[str]) -> list[LfsProgress]:
    """Parse LFS progress lines from stdout/stderr."""
    progress: list[LfsProgress] = []
    for line in lines:
        match = PROGRESS_RE.search(line)
        if not match:
            continue
        progress.append(
            LfsProgress(
                completed_iterations=int(match.group(1)),
                requested_iterations=int(match.group(2)),
                loss=float(match.group(3)),
                splats=int(match.group(4)),
            )
        )
    return progress


def find_patch_output(output_dir: Path, patch_id: str) -> Path | None:
    """Return the highest-iteration patch PLY if present."""
    candidates = list(output_dir.glob(f"{patch_id}_splat_*.ply")) + list(output_dir.glob("splat_*.ply"))
    if not candidates:
        return None

    def iteration(path: Path) -> int:
        match = re.search(r"splat_(\d+)\.ply$", path.name)
        return int(match.group(1)) if match else -1

    return sorted(candidates, key=lambda path: (iteration(path), path.name))[-1]


def classify_lfs_status(
    *,
    patch_id: str,
    requested_iterations: int,
    return_code: int,
    output_dir: Path,
    progress: list[LfsProgress],
    severe_completion_threshold: float,
    parser_warnings: list[str] | None = None,
) -> dict[str, object]:
    """Classify one patch training attempt."""
    final = progress[-1] if progress else None
    output_file = find_patch_output(output_dir, patch_id)
    completed = final.completed_iterations if final else 0
    total = final.requested_iterations if final else requested_iterations
    ratio = completed / total if total else 0.0
    status = "failed"
    reason = "no_usable_output"
    if output_file is not None and return_code == 0 and ratio >= 1.0:
        status = "complete"
        reason = "completed_requested_iterations"
    elif output_file is not None and ratio >= severe_completion_threshold:
        status = "warning"
        reason = "partial_output_above_threshold"
    elif output_file is not None:
        status = "severe_warning"
        reason = "partial_output_below_threshold"
    elif return_code != 0:
        reason = f"lfs_exit_{return_code}"
    return {
        "patch_id": patch_id,
        "requested_iterations": requested_iterations,
        "completed_iterations": completed,
        "completion_ratio": ratio,
        "final_loss": final.loss if final else None,
        "final_splat_count": final.splats if final else None,
        "output_file": str(output_file) if output_file else None,
        "return_code": return_code,
        "status": status,
        "reason": reason,
        "parser_warnings": parser_warnings or [],
    }
