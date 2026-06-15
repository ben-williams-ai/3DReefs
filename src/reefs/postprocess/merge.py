"""Merge cleaned patch PLYs into one site-level PLY using wildflow."""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from reefs.config.models import SplatMergeConfig
from reefs.postprocess.artifacts import CleanupRecord


@dataclass(frozen=True)
class MergeInputRecord:
    """One patch input decision for merge."""

    patch_id: str
    cleaned_file: Path | None
    included: bool
    excluded_reason: str | None
    source_severity: str
    incomplete_source: bool

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable input record."""
        return {
            "patch_id": self.patch_id,
            "cleaned_file": str(self.cleaned_file) if self.cleaned_file else None,
            "included": self.included,
            "excluded_reason": self.excluded_reason,
            "source_severity": self.source_severity,
            "incomplete_source": self.incomplete_source,
        }


@dataclass(frozen=True)
class MergeStatus:
    """Merged site-level PLY status."""

    status: str
    output_file: Path
    inputs: list[MergeInputRecord]
    included_count: int
    excluded_count: int
    severe_warning_count: int
    duration_seconds: float | None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable merge status."""
        return {
            "status": self.status,
            "output_file": str(self.output_file),
            "inputs": [item.as_dict() for item in self.inputs],
            "included_count": self.included_count,
            "excluded_count": self.excluded_count,
            "severe_warning_count": self.severe_warning_count,
            "duration_seconds": self.duration_seconds,
            "warnings": self.warnings,
        }


def build_merge_inputs(
    *,
    cleanup_records: list[CleanupRecord],
    config: SplatMergeConfig,
) -> list[MergeInputRecord]:
    """Build merge input records from cleanup statuses."""
    requested = set(config.patch_ids or [])
    records: list[MergeInputRecord] = []
    for record in cleanup_records:
        if requested and record.patch_id not in requested:
            continue
        output_file = record.output_file if record.output_file and record.output_file.exists() else None
        included = record.status in {"complete", "reused"} and output_file is not None
        reason = None if included else f"cleanup_status_{record.status}"
        records.append(
            MergeInputRecord(
                patch_id=record.patch_id,
                cleaned_file=output_file,
                included=included,
                excluded_reason=reason,
                source_severity=record.source.severity,
                incomplete_source=record.source.severity in {"warning", "severe_warning"},
            )
        )
    return records


def build_merge_params(inputs: list[Path], output_file: Path) -> dict[str, object]:
    """Build wildflow merge parameters."""
    return {
        "input_files": [str(path) for path in inputs],
        "output_file": str(output_file),
    }


def _run_wildflow_merge(params: dict[str, object]) -> None:
    module = importlib.import_module("wildflow.splat")
    module.merge_ply_files(params)


def run_merge(
    *,
    cleanup_records: list[CleanupRecord],
    config: SplatMergeConfig,
    output_file: Path,
) -> MergeStatus:
    """Merge cleaned PLYs and return structured status."""
    inputs = build_merge_inputs(cleanup_records=cleanup_records, config=config)
    included = [record for record in inputs if record.included and record.cleaned_file is not None]
    excluded = [record for record in inputs if not record.included]
    warnings = [
        f"{record.patch_id} excluded from merge: {record.excluded_reason}"
        for record in excluded
    ]
    severe = [record for record in included if record.source_severity == "severe_warning"]
    if severe:
        warnings.append("Severe incomplete sources included in merge: " + ", ".join(item.patch_id for item in severe))
    if not included:
        return MergeStatus(
            status="failed",
            output_file=output_file,
            inputs=inputs,
            included_count=0,
            excluded_count=len(excluded),
            severe_warning_count=len(severe),
            duration_seconds=None,
            warnings=[*warnings, "No cleaned patch PLYs available for merge"],
        )
    if excluded and not config.continue_with_available:
        return MergeStatus(
            status="failed",
            output_file=output_file,
            inputs=inputs,
            included_count=len(included),
            excluded_count=len(excluded),
            severe_warning_count=len(severe),
            duration_seconds=None,
            warnings=[*warnings, "Merge blocked because cleaned outputs are missing"],
        )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    params = build_merge_params([record.cleaned_file for record in included if record.cleaned_file], output_file)
    start = perf_counter()
    failure: str | None = None
    try:
        _run_wildflow_merge(params)
    except Exception as exc:
        failure = str(exc)
    duration = round(perf_counter() - start, 6)
    status = "complete" if failure is None and output_file.exists() else "failed"
    if failure:
        warnings.append(f"wildflow merge failed: {failure}")
    elif status == "failed":
        warnings.append("wildflow merge did not create the expected output file")
    return MergeStatus(
        status=status,
        output_file=output_file,
        inputs=inputs,
        included_count=len(included),
        excluded_count=len(excluded),
        severe_warning_count=len(severe),
        duration_seconds=duration,
        warnings=warnings,
    )
