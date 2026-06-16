"""Post-processing artefact discovery and PLY helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from reefs.io.yaml_json import read_json

ITERATION_RE = re.compile(r"(?:^|_)splat_(\d+)\.ply$")


@dataclass(frozen=True)
class PatchTrainingSource:
    """A trained patch splat selected for cleanup."""

    patch_id: str
    patch_dir: Path
    source_file: Path | None
    source_kind: str
    requested_iterations: int | None
    completed_iterations: int | None
    completion_ratio: float | None
    severity: str
    usable: bool
    reason: str

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable source record."""
        return {
            "patch_id": self.patch_id,
            "patch_dir": str(self.patch_dir),
            "source_file": str(self.source_file) if self.source_file else None,
            "source_kind": self.source_kind,
            "requested_iterations": self.requested_iterations,
            "completed_iterations": self.completed_iterations,
            "completion_ratio": self.completion_ratio,
            "severity": self.severity,
            "usable": self.usable,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CleanupRecord:
    """Per-patch cleanup outcome."""

    patch_id: str
    source: PatchTrainingSource
    output_file: Path | None
    status: str
    cleanup_settings: dict[str, object]
    before_splat_count: int | None = None
    after_splat_count: int | None = None
    duration_seconds: float | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable cleanup record."""
        return {
            "patch_id": self.patch_id,
            "source": self.source.as_dict(),
            "output_file": str(self.output_file) if self.output_file else None,
            "status": self.status,
            "cleanup_settings": self.cleanup_settings,
            "before_splat_count": self.before_splat_count,
            "after_splat_count": self.after_splat_count,
            "duration_seconds": self.duration_seconds,
            "warnings": self.warnings,
        }


def ply_vertex_count(path: Path) -> int | None:
    """Return the vertex count from a PLY header when available."""
    if not path.exists():
        return None
    with path.open("rb") as handle:
        for raw_line in handle:
            line = raw_line.decode("ascii", errors="ignore").strip()
            if line.startswith("element vertex "):
                parts = line.split()
                if len(parts) == 3 and parts[2].isdigit():
                    return int(parts[2])
            if line == "end_header":
                return None
    return None


def output_iteration(path: Path) -> int | None:
    """Return the iteration encoded in a splat PLY filename."""
    match = ITERATION_RE.search(path.name)
    return int(match.group(1)) if match else None


def cleaned_output_for(source_file: Path) -> Path:
    """Return the deterministic cleaned output path for a source PLY."""
    return source_file.with_name(f"{source_file.stem}_clean.ply")


def _training_status(patch_dir: Path) -> dict[str, Any]:
    status_path = patch_dir / "splat" / "training_status.json"
    if not status_path.exists():
        return {}
    try:
        data = read_json(status_path)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _completion_from_status(status: dict[str, Any], output_file: Path | None) -> tuple[int | None, int | None, float | None]:
    requested = status.get("requested_iterations")
    completed = status.get("completed_iterations")
    if completed is None and output_file is not None:
        completed = output_iteration(output_file)
    try:
        requested_int = int(requested) if requested is not None else None
    except (TypeError, ValueError):
        requested_int = None
    try:
        completed_int = int(completed) if completed is not None else None
    except (TypeError, ValueError):
        completed_int = None
    ratio = None
    if requested_int and completed_int is not None:
        ratio = completed_int / requested_int
    return requested_int, completed_int, ratio


def _classify_source(
    *,
    status: dict[str, Any],
    source_file: Path | None,
    source_kind: str,
    requested: int | None,
    ratio: float | None,
    severe_threshold: float,
) -> tuple[str, str, bool]:
    if source_file is None:
        return "failed", "no_usable_ply", False
    status_name = str(status.get("status", ""))
    if source_kind == "finished" or status_name == "complete":
        return "normal", "completed_training_output", True
    if ratio is not None:
        if ratio >= 1.0:
            return "normal", "completed_requested_iterations", True
        if ratio >= severe_threshold:
            return "warning", "partial_output_above_threshold", True
        return "severe_warning", "partial_output_below_threshold", True
    if requested is None:
        return "warning", "unknown_training_completion", True
    return "severe_warning", "partial_output_unknown_completion", True


def discover_patch_training_sources(
    *,
    patches_dir: Path,
    patch_ids: list[str] | None = None,
    severe_threshold: float = 0.80,
) -> list[PatchTrainingSource]:
    """Select post-processing sources from Feature 3 patch outputs."""
    if not patches_dir.exists():
        return []
    patch_dirs = sorted(path for path in patches_dir.iterdir() if path.is_dir())
    if patch_ids:
        selected = set(patch_ids)
        patch_dirs = [path for path in patch_dirs if path.name in selected]
    sources: list[PatchTrainingSource] = []
    for patch_dir in patch_dirs:
        patch_id = patch_dir.name
        splat_dir = patch_dir / "splat"
        status = _training_status(patch_dir)
        finished = splat_dir / "splat_finished.ply"
        source_file: Path | None = finished if finished.exists() else None
        source_kind = "finished" if source_file else "iteration"
        if source_file is None and splat_dir.exists():
            candidates = [path for path in splat_dir.glob("*splat_*.ply") if "_clean" not in path.stem]
            candidates = [path for path in candidates if output_iteration(path) is not None]
            if candidates:
                source_file = sorted(candidates, key=lambda path: (output_iteration(path) or -1, path.name))[-1]
        requested, completed, ratio = _completion_from_status(status, source_file)
        severity, reason, usable = _classify_source(
            status=status,
            source_file=source_file,
            source_kind=source_kind,
            requested=requested,
            ratio=ratio,
            severe_threshold=severe_threshold,
        )
        sources.append(
            PatchTrainingSource(
                patch_id=patch_id,
                patch_dir=patch_dir,
                source_file=source_file,
                source_kind=source_kind,
                requested_iterations=requested,
                completed_iterations=completed,
                completion_ratio=ratio,
                severity=severity,
                usable=usable,
                reason=reason,
            )
        )
    return sources
