"""Top-level foundation preflight orchestration."""

from __future__ import annotations

from dataclasses import dataclass

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


def start_run_log(run_paths: RunPaths, message: str = "Pipeline run started") -> RunLogger:
    """Create append-safe logs for a run."""
    logger = RunLogger(run_paths.pipeline_log, run_paths.warnings_log)
    logger.info(message)
    return logger
