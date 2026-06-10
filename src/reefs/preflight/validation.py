"""Top-level foundation preflight orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reefs.config.models import DerivedPaths
from reefs.io.yaml_json import write_json, write_yaml
from reefs.logging.run_logger import RunLogger
from reefs.logging.timings import TimingRecorder
from reefs.preflight.images import ImageLayout
from reefs.runs.manifest import RunPaths
from reefs.runs.status import RunStatus


@dataclass
class PreflightResult:
    """Result values collected during foundation preflight."""

    image_layout: ImageLayout
    tool_results: list[dict[str, object]]
    resume_events: list[dict[str, object]]
    config_diff_events: list[dict[str, object]]


def write_preflight_report(
    path: Path,
    *,
    derived_paths: DerivedPaths,
    requested_steps: list[str],
    result: PreflightResult,
) -> None:
    """Write a compact human-readable preflight report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Foundation Preflight Report",
        "",
        f"- Project directory: {derived_paths.project_dir}",
        f"- Raw images: {derived_paths.raw_images}",
        f"- Recoloured images: {derived_paths.recoloured_images}",
        f"- Runs directory: {derived_paths.runs}",
        f"- Camera layout: {result.image_layout.kind}",
        f"- Requested steps: {', '.join(requested_steps)}",
        f"- Tool checks: {len(result.tool_results)}",
        f"- Resume events: {len(result.resume_events)}",
        f"- Config diff events: {len(result.config_diff_events)}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_foundation_records(
    *,
    run_paths: RunPaths,
    effective_config_data: dict[str, object],
    cli_overrides_record: dict[str, object],
    manifest: dict[str, object],
    status: RunStatus,
    timings: TimingRecorder,
) -> None:
    """Write the common foundation run records."""
    write_yaml(run_paths.effective_config, effective_config_data)
    write_json(run_paths.cli_overrides, cli_overrides_record)
    write_json(run_paths.manifest, manifest)
    write_json(run_paths.status, status.as_dict())
    write_json(run_paths.timings, timings.as_dict())


def start_run_log(run_paths: RunPaths) -> RunLogger:
    """Create append-safe logs for a run."""
    logger = RunLogger(run_paths.pipeline_log, run_paths.warnings_log)
    logger.info("Foundation preflight started")
    return logger
