"""Run directory and manifest helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reefs.logging.timings import utc_now


@dataclass(frozen=True)
class RunPaths:
    """Filesystem locations for one run record."""

    run_id: str
    run_dir: Path
    effective_config: Path
    cli_overrides: Path
    manifest: Path
    status: Path
    timings: Path
    logs_dir: Path
    pipeline_log: Path
    warnings_log: Path


def create_run_paths(runs_dir: Path, run_id: str | None = None) -> RunPaths:
    """Create run directories and return required record paths."""
    chosen_run_id = run_id or utc_now().replace(":", "").replace("+00:00", "Z")
    run_dir = runs_dir / chosen_run_id
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=False)
    return RunPaths(
        run_id=chosen_run_id,
        run_dir=run_dir,
        effective_config=run_dir / "effective_config.yml",
        cli_overrides=run_dir / "cli_overrides.json",
        manifest=run_dir / "run_manifest.json",
        status=run_dir / "run_status.json",
        timings=run_dir / "timings.json",
        logs_dir=logs_dir,
        pipeline_log=logs_dir / "pipeline.log",
        warnings_log=logs_dir / "warnings.log",
    )


def build_manifest(
    *,
    run_paths: RunPaths,
    source_config_path: Path,
    project_dir: Path,
    requested_steps: list[str],
    tool_versions: dict[str, object],
    resume_events: list[dict[str, object]],
    config_diff_events: list[dict[str, object]],
) -> dict[str, object]:
    """Build the run manifest payload."""
    return {
        "run_id": run_paths.run_id,
        "created_at": utc_now(),
        "source_config_path": str(source_config_path),
        "project_dir": str(project_dir),
        "effective_config_path": str(run_paths.effective_config),
        "cli_overrides_path": str(run_paths.cli_overrides),
        "tool_versions": tool_versions,
        "resume_events": resume_events,
        "config_diff_events": config_diff_events,
        "requested_steps": requested_steps,
    }


def build_cli_overrides_record(
    *,
    overrides: list[dict[str, object]],
    project_dir_override: Path | None,
    requested_steps: list[str] | None,
    resume_policy: str | None,
) -> dict[str, object]:
    """Build the CLI override record."""
    return {
        "overrides": overrides,
        "project_dir_override": str(project_dir_override) if project_dir_override else None,
        "requested_steps": requested_steps,
        "resume_policy": resume_policy,
    }
