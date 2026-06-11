"""Durable run-record writer for long pipeline jobs."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from reefs.io.yaml_json import write_json, write_yaml
from reefs.logging.timings import TimingRecorder, utc_now
from reefs.runs.manifest import RunPaths
from reefs.runs.status import RunStatus


class RunRecorder:
    """Persist run records as soon as state changes.

    Long COLMAP and LFS stages may be interrupted externally, so the pipeline
    cannot wait until the end of a run to write status records.
    """

    def __init__(
        self,
        *,
        run_paths: RunPaths,
        effective_config_data: dict[str, object],
        cli_overrides_record: dict[str, object],
        manifest: dict[str, object],
        status: RunStatus,
        timings: TimingRecorder,
    ) -> None:
        self.run_paths = run_paths
        self.effective_config_data = effective_config_data
        self.cli_overrides_record = cli_overrides_record
        self.manifest = deepcopy(manifest)
        self.status = status
        self.timings = timings
        self.timings.on_update = self.write_timings

    def write_static_records(self) -> None:
        """Write config and override records."""
        write_yaml(self.run_paths.effective_config, self.effective_config_data)
        write_json(self.run_paths.cli_overrides, self.cli_overrides_record)

    def write_manifest(self) -> None:
        """Write the current manifest."""
        self.manifest["updated_at"] = utc_now()
        write_json(self.run_paths.manifest, self.manifest)

    def write_status(self) -> None:
        """Write the current status."""
        write_json(self.run_paths.status, self.status.as_dict())

    def write_timings(self) -> None:
        """Write the current timings."""
        write_json(self.run_paths.timings, self.timings.as_dict())

    def write_all(self) -> None:
        """Write every run record."""
        self.write_static_records()
        self.write_manifest()
        self.write_status()
        self.write_timings()

    def update_manifest(self, **updates: Any) -> None:
        """Merge top-level manifest updates and persist them."""
        self.manifest.update(updates)
        self.write_manifest()

    def stage_started(self, stage: str, *, command_args: list[str] | None = None) -> None:
        """Persist that a stage has started."""
        self.status.mark_stage(stage)
        if command_args is not None:
            self.status.mark_active_command(stage=stage, args=command_args)
        self.write_status()

    def stage_completed(self, stage: str) -> None:
        """Persist that a stage has completed."""
        self.status.complete_stage(stage)
        self.write_status()

    def stage_failed(self, stage: str, error: str) -> None:
        """Persist that a stage has failed."""
        self.status.current_stage = stage
        self.status.fail(error)
        self.write_status()
