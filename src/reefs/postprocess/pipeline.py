"""Post-processing orchestration for cleaned splats, merge, and SOG."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from reefs.io.yaml_json import write_json
from reefs.logging.timings import TimingRecorder, utc_now
from reefs.postprocess.artifacts import CleanupRecord, discover_patch_training_sources
from reefs.postprocess.cleanup import clean_patch_source, cleanup_settings
from reefs.postprocess.merge import MergeStatus, run_merge
from reefs.postprocess.resume import apply_postprocess_overwrite_decisions
from reefs.postprocess.sog import SogStatus, run_sog_export
from reefs.preflight.splat import SplatPreflightResult
from reefs.runs.recorder import RunRecorder


@dataclass
class PostprocessResult:
    """Structured post-processing result."""

    requested_stages: list[str]
    cleanup: list[CleanupRecord] = field(default_factory=list)
    merge: MergeStatus | None = None
    sog: SogStatus | None = None
    warnings: list[str] = field(default_factory=list)
    output_events: list[dict[str, object]] = field(default_factory=list)
    manifest_path: Path | None = None
    status: str = "not_started"

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable result."""
        return {
            "requested_stages": self.requested_stages,
            "cleanup": [item.as_dict() for item in self.cleanup],
            "merge": self.merge.as_dict() if self.merge else None,
            "sog": self.sog.as_dict() if self.sog else None,
            "warnings": self.warnings,
            "output_events": self.output_events,
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "status": self.status,
        }


def _write_manifest(preflight_result: SplatPreflightResult, result: PostprocessResult, config) -> None:
    preflight_result.paths.postprocess.mkdir(parents=True, exist_ok=True)
    result.manifest_path = preflight_result.paths.postprocess_manifest
    data = {
        "updated_at": utc_now(),
        "requested_stages": result.requested_stages,
        "effective_settings": {
            "cleanup": config.advanced.splat.cleanup.model_dump(mode="json"),
            "merge": config.advanced.splat.merge.model_dump(mode="json"),
            "sog": config.advanced.splat.sog.model_dump(mode="json"),
        },
        "cleanup": [item.as_dict() for item in result.cleanup],
        "merge": result.merge.as_dict() if result.merge else None,
        "sog": result.sog.as_dict() if result.sog else None,
        "warnings": result.warnings,
        "output_events": result.output_events,
        "status": result.status,
    }
    write_json(preflight_result.paths.postprocess_manifest, data)


def _warning_summary(result: PostprocessResult) -> list[str]:
    warnings = list(result.warnings)
    for item in result.cleanup:
        if item.source.severity == "severe_warning":
            warnings.append(f"Severe incomplete source used for {item.patch_id}: {item.source.source_file}")
        warnings.extend(item.warnings)
    if result.merge:
        warnings.extend(result.merge.warnings)
    if result.sog and result.sog.status == "failed":
        warnings.append(f"Final SOG failed: {result.sog.failure_reason}")
    return list(dict.fromkeys(str(warning) for warning in warnings if warning))


def run_postprocess_pipeline(
    *,
    config,
    preflight_result: SplatPreflightResult,
    stages: list[str],
    timings: TimingRecorder,
    recorder: RunRecorder | None,
) -> PostprocessResult:
    """Run requested post-processing stages."""
    result = PostprocessResult(requested_stages=stages, status="running")
    result.output_events = apply_postprocess_overwrite_decisions(preflight_result.postprocess_output_decisions)
    _write_manifest(preflight_result, result, config)

    cleanup_records: list[CleanupRecord] = []
    if "splat.cleanup" in stages:
        cleanup_config = config.advanced.splat.cleanup
        sources = discover_patch_training_sources(
            patches_dir=preflight_result.paths.patches,
            patch_ids=cleanup_config.patch_ids,
            severe_threshold=config.advanced.splat.train.severe_completion_threshold,
        )
        if not sources:
            raise ValueError("No Feature 3 patch training outputs found for cleanup")
        for source in sources:
            stage = f"splat.cleanup.{source.patch_id}"
            if recorder:
                recorder.stage_started(stage)
                if recorder.reporter:
                    recorder.reporter.info(f"Cleaning patch {source.patch_id}")
            with timings.stage(stage):
                record = clean_patch_source(
                    source=source,
                    config=cleanup_config,
                )
            cleanup_records.append(record)
            result.cleanup = cleanup_records
            result.warnings = _warning_summary(result)
            _write_manifest(preflight_result, result, config)
            if recorder:
                if record.status == "failed":
                    recorder.status.skip_stage(stage, "failed")
                    recorder.write_status()
                else:
                    recorder.stage_completed(stage)
    else:
        cleanup_records = _load_existing_cleanup_records(config=config, preflight_result=preflight_result)
        result.cleanup = cleanup_records

    if "splat.merge" in stages:
        if recorder:
            recorder.stage_started("splat.merge")
            if recorder.reporter:
                recorder.reporter.info("Merging cleaned patch splats")
        output_name = config.advanced.splat.merge.output_name
        output_file = preflight_result.paths.merged / output_name
        with timings.stage("splat.merge"):
            result.merge = run_merge(
                cleanup_records=cleanup_records,
                config=config.advanced.splat.merge,
                output_file=output_file,
            )
        result.warnings = _warning_summary(result)
        _write_manifest(preflight_result, result, config)
        if recorder:
            if result.merge.status == "complete":
                recorder.stage_completed("splat.merge")
            else:
                recorder.status.skip_stage("splat.merge", result.merge.status)
                recorder.write_status()

    if "splat.sog" in stages:
        if recorder:
            recorder.stage_started("splat.sog")
            if recorder.reporter:
                recorder.reporter.info("Exporting merged splat to SOG")
        source_file = result.merge.output_file if result.merge else preflight_result.paths.merged / config.advanced.splat.merge.output_name
        output_file = preflight_result.paths.sog / config.advanced.splat.sog.output_name
        tool_version = _tool_version(preflight_result)
        with timings.stage("splat.sog"):
            result.sog = run_sog_export(
                splat_transform_bin=config.tools.splat_transform_bin,
                source_file=source_file,
                output_file=output_file,
                config=config.advanced.splat.sog,
                log_path=preflight_result.paths.splat_transform_log,
                tool_version=tool_version,
                reporter=recorder.reporter if recorder else None,
            )
        result.warnings = _warning_summary(result)
        _write_manifest(preflight_result, result, config)
        if recorder:
            if result.sog.status == "complete":
                recorder.stage_completed("splat.sog")
            else:
                recorder.status.skip_stage("splat.sog", result.sog.status)
                recorder.write_status()

    result.warnings = _warning_summary(result)
    result.status = _overall_status(result)
    _write_manifest(preflight_result, result, config)
    return result


def _tool_version(preflight_result: SplatPreflightResult) -> str | None:
    for item in preflight_result.tool_results:
        if item.get("tool_name") == "splat-transform":
            version = item.get("detected_version")
            return str(version) if version is not None else None
    return None


def _overall_status(result: PostprocessResult) -> str:
    if result.sog and result.sog.status == "failed" and result.merge and result.merge.status == "complete":
        return "partial"
    if any(item.status == "failed" for item in result.cleanup):
        return "partial"
    if result.merge and result.merge.status == "failed":
        return "failed"
    if result.sog and result.sog.status == "failed":
        return "failed"
    return "complete"


def _load_existing_cleanup_records(*, config, preflight_result: SplatPreflightResult) -> list[CleanupRecord]:
    sources = discover_patch_training_sources(
        patches_dir=preflight_result.paths.patches,
        patch_ids=config.advanced.splat.merge.patch_ids,
        severe_threshold=config.advanced.splat.train.severe_completion_threshold,
    )
    records: list[CleanupRecord] = []
    for source in sources:
        output_file = source.source_file.with_name(f"{source.source_file.stem}_clean.ply") if source.source_file else None
        status = "reused" if output_file and output_file.exists() else "skipped"
        records.append(
            CleanupRecord(
                patch_id=source.patch_id,
                source=source,
                output_file=output_file if output_file and output_file.exists() else None,
                status=status,
                cleanup_settings=cleanup_settings(config.advanced.splat.cleanup),
                warnings=[] if status == "reused" else ["cleaned_output_missing"],
            )
        )
    return records
