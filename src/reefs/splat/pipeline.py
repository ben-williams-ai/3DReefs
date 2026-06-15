"""Splat patching and training pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from reefs.diagnostics.patch_plots import write_outlier_pose_diagnostics, write_patch_selection_diagnostics, write_patch_summary
from reefs.io.yaml_json import write_json
from reefs.io.yaml_json import read_json
from reefs.lfs.runner import run_lfs_training
from reefs.logging.timings import TimingRecorder
from reefs.patches.artefacts import ensure_text_sparse_model, read_sparse_scene_text
from reefs.patches.bounds import generate_patch_bounds
from reefs.patches.export import export_patch_dataset, write_sparse_subset_by_image_ids
from reefs.patches.outliers import detect_camera_pose_outliers
from reefs.patches.selection import select_patch_views
from reefs.patches.validation import validate_patch_metadata
from reefs.preflight.splat import SplatPreflightResult
from reefs.postprocess.pipeline import PostprocessResult, run_postprocess_pipeline
from reefs.runs.recorder import RunRecorder
from reefs.splat.resume import apply_overwrite_decisions, materialise_patch_affecting_config
from reefs.splat.validation import SplatPaths, expand_splat_steps


@dataclass
class SplatRunResult:
    """Outputs and metadata from a splat invocation."""

    paths: SplatPaths
    requested_stages: list[str]
    warnings: list[str] = field(default_factory=list)
    output_events: list[dict[str, object]] = field(default_factory=list)
    patches: list[dict[str, object]] = field(default_factory=list)
    outlier_filter: dict[str, object] | None = None
    training: list[dict[str, object]] = field(default_factory=list)
    postprocess: dict[str, object] | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable result."""
        return {
            "paths": {
                "root": str(self.paths.root),
                "outlier_filter": str(self.paths.outlier_filter),
                "filtered_sparse": str(self.paths.filtered_sparse),
                "patches": str(self.paths.patches),
                "training": str(self.paths.training),
                "postprocess": str(self.paths.postprocess),
                "postprocess_manifest": str(self.paths.postprocess_manifest),
                "merged": str(self.paths.merged),
                "merged_ply": str(self.paths.merged_ply),
                "sog": str(self.paths.sog),
                "final_sog": str(self.paths.final_sog),
                "lfs_log": str(self.paths.lfs_log),
                "splat_transform_log": str(self.paths.splat_transform_log),
            },
            "requested_stages": self.requested_stages,
            "warnings": self.warnings,
            "output_events": self.output_events,
            "patches": self.patches,
            "outlier_filter": self.outlier_filter,
            "training": self.training,
            "postprocess": self.postprocess,
        }


def _runnable_splat_stages(requested_steps: list[str]) -> list[str]:
    """Return non-preflight splat stages requested for this invocation."""
    expanded = expand_splat_steps(requested_steps)
    return [stage for stage in expanded if stage.startswith("splat.") and stage != "splat.preflight"]


def run_splat_pipeline(
    *,
    config,
    preflight_result: SplatPreflightResult,
    requested_steps: list[str],
    timings: TimingRecorder,
    recorder: RunRecorder | None = None,
) -> SplatRunResult:
    """Run requested splat stages currently implemented by Feature 3."""
    stages = _runnable_splat_stages(requested_steps)
    output_events = apply_overwrite_decisions(preflight_result.output_decisions)
    if recorder and output_events:
        recorder.update_manifest(
            generated_output_events=[
                *recorder.manifest.get("generated_output_events", []),
                *output_events,
            ]
        )

    result = SplatRunResult(
        paths=preflight_result.paths,
        requested_stages=stages,
        warnings=list(preflight_result.warnings),
        output_events=output_events,
    )
    source_sparse, scene = _prepare_patch_source(preflight_result)
    if _should_run_outlier_filter(config=config, stages=stages):
        if recorder:
            recorder.stage_started("splat.outlier_filter")
        with timings.stage("splat.outlier_filter"):
            source_sparse, scene, result.outlier_filter = _run_outlier_filter(
                config=config,
                preflight_result=preflight_result,
                source_sparse=source_sparse,
                scene=scene,
            )
        if recorder:
            recorder.stage_completed("splat.outlier_filter")

    if "splat.patch" in stages:
        if recorder:
            recorder.stage_started("splat.patch")
        with timings.stage("splat.patch"):
            result.patches.extend(
                _generate_patches(
                    config=config,
                    preflight_result=preflight_result,
                    source_sparse=source_sparse,
                    scene=scene,
                )
            )
        if recorder:
            recorder.stage_completed("splat.patch")

    if "splat.train" in stages:
        if recorder:
            recorder.stage_started("splat.train")
        with timings.stage("splat.train"):
            training_results = _train_patches(config=config, preflight_result=preflight_result)
            result.patches = result.patches or _load_patch_records(preflight_result.paths.patches)
            write_json(preflight_result.paths.training / "training_manifest.json", training_results)
            result.training = training_results
        if recorder:
            recorder.stage_completed("splat.train")

    postprocess_stages = [stage for stage in stages if stage in {"splat.cleanup", "splat.merge", "splat.sog"}]
    if postprocess_stages:
        postprocess_result = run_postprocess_pipeline(
            config=config,
            preflight_result=preflight_result,
            stages=postprocess_stages,
            timings=timings,
            recorder=recorder,
        )
        result.postprocess = postprocess_result.as_dict()
        result.warnings.extend(postprocess_result.warnings)
        if recorder:
            recorder.update_manifest(
                postprocess={
                    "manifest": str(preflight_result.paths.postprocess_manifest),
                    "status": postprocess_result.status,
                    "merged_ply": (
                        str(postprocess_result.merge.output_file)
                        if postprocess_result.merge
                        else str(preflight_result.paths.merged / config.advanced.splat.merge.output_name)
                    ),
                    "sog": (
                        str(postprocess_result.sog.output_sog)
                        if postprocess_result.sog
                        else str(preflight_result.paths.sog / config.advanced.splat.sog.output_name)
                    ),
                }
            )

    known_stages = {"splat.outlier_filter", "splat.patch", "splat.train", "splat.cleanup", "splat.merge", "splat.sog"}
    for stage in [stage for stage in stages if stage not in known_stages]:
        if recorder:
            recorder.status.skip_stage(stage, "not_implemented_yet")
            recorder.write_status()
        result.warnings.append(f"{stage} is routed but not implemented in the current Feature 3 slice.")
    return result


def _patch_affecting_config(config) -> dict[str, object]:
    """Return the patch-generation config persisted into patch metadata."""
    return materialise_patch_affecting_config(config)


def _prepare_patch_source(preflight_result: SplatPreflightResult):
    """Prepare a text sparse source and parsed scene for splat stages."""
    source_sparse = ensure_text_sparse_model(
        preflight_result.source.paths.sparse_dir,
        preflight_result.paths.root / "source_sparse_txt",
    )
    return source_sparse, read_sparse_scene_text(source_sparse)


def _should_run_outlier_filter(*, config, stages: list[str]) -> bool:
    """Return whether outlier filtering should run for this invocation."""
    if "splat.outlier_filter" in stages:
        return True
    return config.advanced.splat.outlier_filter.enabled and "splat.patch" in stages


def _run_outlier_filter(
    *,
    config,
    preflight_result: SplatPreflightResult,
    source_sparse,
    scene,
) -> tuple[object, object, dict[str, object]]:
    """Run camera-pose outlier filtering and return the sparse source for patching."""
    filter_config = config.advanced.splat.outlier_filter
    result = detect_camera_pose_outliers(
        scene,
        method=filter_config.method,
        iqr_mult=filter_config.iqr_mult,
        percentile=filter_config.percentile,
        max_removal_fraction=filter_config.max_removal_fraction,
        dry_run=filter_config.dry_run,
    )
    diagnostics_dir = preflight_result.paths.outlier_filter / "diagnostics"
    diagnostic_warnings = write_outlier_pose_diagnostics(result, diagnostics_dir)
    summary = {
        **result.as_dict(),
        "filter_enabled": filter_config.enabled,
        "dry_run": filter_config.dry_run,
        "source_sparse": str(source_sparse),
        "filtered_sparse": str(preflight_result.paths.filtered_sparse / "0"),
        "diagnostics": {
            "camera_pose_top_before": str(diagnostics_dir / "camera_pose_top_before.png"),
            "camera_pose_top_after": str(diagnostics_dir / "camera_pose_top_after.png"),
            "camera_pose_side_before": str(diagnostics_dir / "camera_pose_side_before.png"),
            "camera_pose_side_after": str(diagnostics_dir / "camera_pose_side_after.png"),
        },
        "warnings": [*result.warnings, *diagnostic_warnings],
    }
    write_json(preflight_result.paths.outlier_filter / "filter_summary.json", summary)
    if result.state == "blocked_ambiguous":
        raise ValueError("Outlier filtering blocked patching as ambiguous: " + "; ".join(summary["warnings"]))
    if not filter_config.dry_run:
        filtered_sparse = preflight_result.paths.filtered_sparse / "0"
        write_sparse_subset_by_image_ids(
            scene=scene,
            source_sparse=source_sparse,
            destination=filtered_sparse,
            kept_image_ids=result.kept_image_ids,
        )
        return filtered_sparse, read_sparse_scene_text(filtered_sparse), summary
    return source_sparse, scene, summary


def _generate_patches(
    *,
    config,
    preflight_result: SplatPreflightResult,
    source_sparse,
    scene,
) -> list[dict[str, object]]:
    """Generate patch datasets from the selected source reconstruction."""
    patch_config = config.advanced.splat.patching
    bounds = generate_patch_bounds(
        scene.images,
        max_cameras=patch_config.max_cameras,
        buffer=patch_config.buffer,
        points_xyz=[point.xyz for point in scene.points],
    )
    all_bounds = list(bounds)
    if patch_config.patch_ids:
        requested_ids = set(patch_config.patch_ids)
        unknown = sorted(requested_ids - {item.patch_id for item in bounds})
        if unknown:
            raise ValueError("Requested patch ids do not exist: " + ", ".join(unknown))
        bounds = [item for item in bounds if item.patch_id in requested_ids]

    preflight_result.paths.patches.mkdir(parents=True, exist_ok=True)
    summary_warnings = write_patch_summary(scene, all_bounds, preflight_result.paths.patches / "patch_summary.png")
    patch_records: list[dict[str, object]] = []
    for item in bounds:
        selection = select_patch_views(scene, item, max_cameras=patch_config.max_cameras, all_bounds=all_bounds)
        patch_dir = preflight_result.paths.patches / item.patch_id
        metadata = export_patch_dataset(
            selection=selection,
            source_sparse=source_sparse,
            image_root=preflight_result.source.paths.images_dir,
            patch_dir=patch_dir,
            source_run_id=preflight_result.source.paths.images_dir.parents[2].name,
            patch_affecting_config=_patch_affecting_config(config),
        )
        diagnostic_warnings = write_patch_selection_diagnostics(selection, patch_dir / "patch_diagnostics")
        all_diagnostic_warnings = [*summary_warnings, *diagnostic_warnings]
        if all_diagnostic_warnings:
            metadata["warnings"] = [*list(metadata.get("warnings") or []), *all_diagnostic_warnings]
            write_json(patch_dir / "patch_metadata.json", metadata)
        metadata = validate_patch_metadata(patch_dir, max_cameras=patch_config.max_cameras)
        patch_records.append(metadata)
    return patch_records


def _load_patch_records(patches_dir) -> list[dict[str, object]]:
    """Load patch metadata records from a patches directory."""
    if not patches_dir.exists():
        return []
    records: list[dict[str, object]] = []
    for metadata_path in sorted(patches_dir.glob("*/patch_metadata.json")):
        data = read_json(metadata_path)
        if isinstance(data, dict):
            records.append(data)
    return records


def _selected_training_patch_records(config, patches_dir) -> list[dict[str, object]]:
    """Return patch metadata records selected for training."""
    records = _load_patch_records(patches_dir)
    if not records:
        raise ValueError("No patch metadata found. Run splat.patch before splat.train.")
    by_id = {str(record["patch_id"]): record for record in records if "patch_id" in record}
    requested = config.advanced.splat.train.patch_ids
    if requested:
        unknown = sorted(set(requested) - set(by_id))
        if unknown:
            raise ValueError("Requested training patch ids do not exist: " + ", ".join(unknown))
        return [by_id[patch_id] for patch_id in requested]
    return [by_id[patch_id] for patch_id in sorted(by_id)]


def _train_patches(*, config, preflight_result: SplatPreflightResult) -> list[dict[str, object]]:
    """Train selected valid patches serially with LFS."""
    train_config = config.advanced.splat.train
    results: list[dict[str, object]] = []
    preflight_result.paths.training.mkdir(parents=True, exist_ok=True)
    for record in _selected_training_patch_records(config, preflight_result.paths.patches):
        patch_id = str(record["patch_id"])
        patch_dir = preflight_result.paths.patches / patch_id
        existing_status_path = patch_dir / "splat" / "training_status.json"
        if existing_status_path.exists() and not train_config.retrain_failed:
            existing = read_json(existing_status_path)
            if isinstance(existing, dict):
                reused = {**existing, "decision": "reuse", "reason": existing.get("reason", "existing_training_status")}
                results.append(reused)
                continue
        if record.get("status") != "valid":
            skipped = {
                "patch_id": patch_id,
                "requested_iterations": train_config.num_iters,
                "completed_iterations": 0,
                "completion_ratio": 0.0,
                "num_splats_per_patch": train_config.num_splats_per_patch,
                "strategy": train_config.strategy,
                "headless": train_config.headless,
                "return_code": None,
                "output_file": None,
                "status": "skipped",
                "reason": "invalid_patch",
                "invalid_reasons": record.get("invalid_reasons", []),
            }
            write_json(patch_dir / "splat" / "training_status.json", skipped)
            results.append(skipped)
            continue
        status = run_lfs_training(
            lfs_bin=config.tools.lfs_bin,
            patch_dir=patch_dir,
            patch_id=patch_id,
            num_iters=train_config.num_iters,
            num_splats_per_patch=train_config.num_splats_per_patch,
            strategy=train_config.strategy,
            headless=train_config.headless,
            lfs_config=train_config.lfs_config,
            lfs_log=preflight_result.paths.lfs_log,
            severe_completion_threshold=train_config.severe_completion_threshold,
        )
        status.update(
            {
                "num_splats_per_patch": train_config.num_splats_per_patch,
                "strategy": train_config.strategy,
                "headless": train_config.headless,
            }
        )
        write_json(patch_dir / "splat" / "training_status.json", status)
        results.append(status)
    return results
