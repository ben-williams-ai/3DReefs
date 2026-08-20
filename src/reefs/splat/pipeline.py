"""Splat patching and training pipeline orchestration."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from reefs.diagnostics.patch_plots import write_outlier_pose_diagnostics, write_patch_selection_diagnostics, write_patch_summary
from reefs.eval.holdout import build_eval_dataset, load_or_create_holdout, normalise_target_image_source
from reefs.colour.pipeline import prepare_corrected_workspace
from reefs.config.models import ColourRestorationMode
from reefs.eval.lfs import run_lfs_eval_attempt
from reefs.io.yaml_json import write_json
from reefs.io.yaml_json import read_json
from reefs.lfs.runner import run_lfs_training
from reefs.logging.timings import TimingRecorder
from reefs.patches.artefacts import ensure_text_sparse_model, read_sparse_scene_text
from reefs.patches.bounds import generate_patch_bounds
from reefs.patches.export import export_patch_dataset, write_sparse_subset_by_image_ids
from reefs.patches.outliers import detect_camera_pose_outliers
from reefs.patches.selection import derive_patch_camera_targets, select_patch_views
from reefs.patches.validation import validate_patch_metadata
from reefs.preflight.splat import SplatPreflightResult
from reefs.postprocess.pipeline import PostprocessResult, run_postprocess_pipeline
from reefs.runs.recorder import RunRecorder
from reefs.splat.resume import apply_overwrite_decisions, materialise_patch_affecting_config
from reefs.splat.validation import SplatPaths, expand_splat_steps

RETRYABLE_LFS_WIDTH_SIGNATURES = (
    "an illegal memory access was encountered",
    "cuda_error_illegal_address",
    "xid 31",
    "signed 32-bit instance overflow",
    "instance count exceeds signed 32-bit",
    "bucket buffer overflow",
    "bucket-buffer overflow",
    "out_of_memory: failed to allocate bucket buffers",
)


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
    eval: list[dict[str, object]] = field(default_factory=list)
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
                "eval": str(self.paths.eval),
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
            "eval": self.eval,
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
    source_sparse = scene = None
    if any(stage in stages for stage in {"splat.outlier_filter", "splat.patch"}):
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

    if "splat.eval" in stages:
        if recorder:
            recorder.stage_started("splat.eval")
        with timings.stage("splat.eval"):
            eval_results = _eval_patches(config=config, preflight_result=preflight_result)
            result.patches = result.patches or _load_patch_records(preflight_result.paths.patches)
            result.eval = eval_results
        if recorder:
            recorder.stage_completed("splat.eval")

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

    known_stages = {
        "splat.outlier_filter",
        "splat.patch",
        "splat.train",
        "splat.eval",
        "splat.cleanup",
        "splat.merge",
        "splat.sog",
    }
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
    if preflight_result.source is None:
        raise ValueError("Splat source reconstruction is required for patch-generation stages")
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
    patch_targets = derive_patch_camera_targets(
        patch_config.max_cameras,
        patch_config.external_support_fraction,
    )
    bounds = generate_patch_bounds(
        scene.images,
        max_cameras=int(patch_targets["internal_patch_target"]),
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
        selection = select_patch_views(
            scene,
            item,
            max_cameras=patch_config.max_cameras,
            all_bounds=all_bounds,
            external_support_fraction=patch_config.external_support_fraction,
        )
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
    metadata_paths = sorted(patches_dir.glob("*/patch_metadata.json")) if patches_dir.exists() else []
    if not metadata_paths:
        raise ValueError("No patch metadata found. Run splat.patch before splat.train.")
    records: list[dict[str, object]] = []
    for metadata_path in metadata_paths:
        records.append(validate_patch_metadata(metadata_path.parent, max_cameras=config.advanced.splat.patching.max_cameras))
    by_id = {str(record["patch_id"]): record for record in records if "patch_id" in record}
    requested = config.advanced.splat.train.patch_ids
    if requested:
        unknown = sorted(set(requested) - set(by_id))
        if unknown:
            raise ValueError("Requested training patch ids do not exist: " + ", ".join(unknown))
        return [by_id[patch_id] for patch_id in requested]
    return [by_id[patch_id] for patch_id in sorted(by_id)]


def _attempt_summary(status: dict[str, object]) -> dict[str, object]:
    """Return stable retry metadata for one LFS attempt."""
    return {
        "max_width": status.get("max_width"),
        "status": status.get("status"),
        "reason": status.get("reason"),
        "completed_iterations": status.get("completed_iterations"),
        "return_code": status.get("return_code"),
        "output_file": status.get("output_file"),
        "log_file": status.get("log_file"),
        "loss_history_file": status.get("loss_history_file"),
    }


def _is_retryable_lfs_width_failure(status: dict[str, object]) -> bool:
    """Return whether an LFS attempt failed in the known width-pressure path."""
    if status.get("status") not in {"failed", "severe_warning"}:
        return False
    text = "\n".join(str(line) for line in status.get("log_tail", []))
    lowered = text.lower()
    return any(signature in lowered for signature in RETRYABLE_LFS_WIDTH_SIGNATURES)


def _run_lfs_training_with_retries(
    *,
    config,
    preflight_result: SplatPreflightResult,
    patch_dir,
    patch_id: str,
) -> dict[str, object]:
    """Run LFS once, then retry known width-pressure failures at configured widths."""
    train_config = config.advanced.splat.train
    attempts: list[dict[str, object]] = []
    widths = [train_config.max_width, *train_config.retry_max_width]
    final_status: dict[str, object] | None = None
    attempts_dir = patch_dir / "splat" / "attempts"

    for index, max_width in enumerate(widths):
        attempt_dir = attempts_dir / f"attempt_{index + 1}"
        suffix = 1
        while attempt_dir.exists():
            suffix += 1
            attempt_dir = attempts_dir / f"attempt_{index + 1}_{suffix}"
        status = run_lfs_training(
            lfs_bin=config.tools.lfs_bin,
            patch_dir=patch_dir,
            patch_id=patch_id,
            num_iters=train_config.num_iters,
            num_splats_per_patch=train_config.num_splats_per_patch,
            strategy=train_config.strategy,
            headless=train_config.headless,
            max_width=max_width,
            lfs_config=train_config.lfs_config,
            lfs_log=preflight_result.paths.lfs_log,
            severe_completion_threshold=train_config.severe_completion_threshold,
            output_dir=attempt_dir,
        )
        status.update(
            {
                "num_splats_per_patch": train_config.num_splats_per_patch,
                "strategy": train_config.strategy,
                "headless": train_config.headless,
                "max_width": max_width,
            }
        )
        attempts.append(_attempt_summary(status))
        final_status = status
        if status.get("status") in {"complete", "warning"}:
            break
        if index == len(widths) - 1:
            final_status["all_retry_widths_exhausted"] = len(widths) > 1
            break
        if not _is_retryable_lfs_width_failure(status):
            final_status["retry_skipped_reason"] = "non_retryable_lfs_failure"
            break

    assert final_status is not None
    final_status["attempts"] = attempts
    final_status["attempted_max_widths"] = [attempt["max_width"] for attempt in attempts]
    if final_status.get("status") == "complete" and isinstance(final_status.get("output_file"), str):
        attempt_output = Path(str(final_status["output_file"]))
        attempt_original = Path(str(final_status["original_output_file"]))
        promoted_original = patch_dir / "splat" / attempt_original.name
        promoted_output = patch_dir / "splat" / "splat_finished.ply"
        promoted_output.parent.mkdir(parents=True, exist_ok=True)
        promoted_original.unlink(missing_ok=True)
        promoted_output.unlink(missing_ok=True)
        promoted_original.hardlink_to(attempt_original)
        promoted_output.hardlink_to(promoted_original)
        final_status["attempt_output_file"] = str(attempt_output)
        final_status["attempt_original_output_file"] = str(attempt_original)
        final_status["original_output_file"] = str(promoted_original)
        final_status["output_file"] = str(promoted_output)
        for field in ("log_file", "loss_history_file"):
            attempt_artifact = Path(str(final_status[field]))
            promoted_artifact = patch_dir / "splat" / attempt_artifact.name
            promoted_artifact.unlink(missing_ok=True)
            promoted_artifact.hardlink_to(attempt_artifact)
            final_status[f"attempt_{field}"] = str(attempt_artifact)
            final_status[field] = str(promoted_artifact)
    return final_status


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
                "max_width": train_config.max_width,
                "return_code": None,
                "output_file": None,
                "status": "skipped",
                "reason": "invalid_patch",
                "invalid_reasons": record.get("invalid_reasons", []),
            }
            write_json(patch_dir / "splat" / "training_status.json", skipped)
            results.append(skipped)
            continue
        status = _run_lfs_training_with_retries(
            config=config,
            preflight_result=preflight_result,
            patch_dir=patch_dir,
            patch_id=patch_id,
        )
        write_json(patch_dir / "splat" / "training_status.json", status)
        results.append(status)
    return results


def _eval_patches(*, config, preflight_result: SplatPreflightResult) -> list[dict[str, object]]:
    """Run explicit LFS eval for selected patch datasets."""
    eval_config = config.advanced.eval
    if not eval_config.enabled:
        raise ValueError("splat.eval requires advanced.eval.enabled: true")
    target_image_source = normalise_target_image_source(eval_config.target_image_source)
    full_res_images_dir = None
    if target_image_source == "full_resolution_undistorted":
        full_res_images_dir = eval_config.full_resolution_undistorted_images_dir
        if full_res_images_dir is None:
            full_res_images_dir = preflight_result.paths.root.parent / "sfm" / "undistorted_full_resolution" / "images"
        if not full_res_images_dir.exists():
            raise ValueError(f"full-resolution undistorted eval images are missing: {full_res_images_dir}")
        if config.colour_restoration.mode in {
            ColourRestorationMode.PROFILE,
            ColourRestorationMode.GRAY_WORLD,
        }:
            full_res_images_dir = prepare_corrected_workspace(
                run_dir=preflight_result.paths.root.parent,
                workspace=full_res_images_dir.parent,
                mode=config.colour_restoration.mode.value,
                profile_path=config.colour_restoration.profile_path,
                overwrite=config.colour_restoration.overwrite,
            )
    train_config = config.advanced.splat.train
    eval_max_width = 0 if target_image_source == "full_resolution_undistorted" else train_config.max_width
    eval_root = preflight_result.paths.eval
    eval_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    long_rows: list[dict[str, object]] = []
    for record in _selected_training_patch_records(config, preflight_result.paths.patches):
        patch_id = str(record["patch_id"])
        patch_dir = preflight_result.paths.patches / patch_id
        holdout_path = eval_root / "holdouts" / f"{patch_id}.json"
        holdout = load_or_create_holdout(
            patch_dir=patch_dir,
            canonical_path=holdout_path,
            holdout_fraction=eval_config.holdout_fraction,
        )
        if holdout.missing_holdout_images:
            raise ValueError(f"canonical holdout images are missing for {patch_id}: {holdout.missing_holdout_images}")
        eval_dataset = eval_root / "datasets" / patch_id
        build_eval_dataset(
            patch_dir=patch_dir,
            output_dir=eval_dataset,
            holdout=holdout,
            target_image_source=target_image_source,
            source_images_dir=full_res_images_dir,
        )
        eval_target = _eval_dataset_fields(eval_dataset / "eval_dataset_manifest.json")
        output_dir = _next_eval_attempt_dir(eval_root / "patches" / patch_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        attempt_name = output_dir.name
        attempt = run_lfs_eval_attempt(
            lfs_bin=config.tools.lfs_bin,
            patch_id=patch_id,
            dataset_dir=eval_dataset,
            output_dir=output_dir,
            num_iters=train_config.num_iters,
            num_splats_per_patch=train_config.num_splats_per_patch,
            strategy=train_config.strategy,
            headless=train_config.headless,
            max_width=eval_max_width,
            base_lfs_config=train_config.lfs_config,
            eval_steps=eval_config.eval_steps,
            test_every=holdout.test_every,
            severe_completion_threshold=train_config.severe_completion_threshold,
            compute_lpips="lpips" in eval_config.metrics,
        )
        for row in attempt.metric_rows:
            long_rows.append(
                {
                    "patch_id": patch_id,
                    "attempt": attempt_name,
                    "iteration": row.get("iteration", ""),
                    "psnr": row.get("psnr", ""),
                    "ssim": row.get("ssim", ""),
                    "lpips": row.get("lpips", ""),
                    "metric_source": row.get("metric_source", ""),
                    **eval_target,
                    "time_per_image": row.get("time_per_image", ""),
                    "num_gaussians": row.get("num_gaussians", ""),
                    "metrics_path": str(attempt.metrics_path),
                }
            )
        status = {
            "patch_id": patch_id,
            **attempt.status,
            "return_code": attempt.return_code,
            "duration_seconds": attempt.duration_seconds,
            "holdout": str(holdout_path),
            "eval_dataset": str(eval_dataset),
            "eval_dataset_manifest": str(eval_dataset / "eval_dataset_manifest.json"),
            "lfs_config": str(attempt.lfs_config),
            "log_file": str(attempt.log_path),
            "metrics_path": str(attempt.metrics_path),
            "metrics": attempt.metrics,
            "eval_target": eval_target,
        }
        write_json(output_dir / "eval_status.json", status)
        results.append(status)
    _write_csv(eval_root / "metrics_long.csv", long_rows)
    _write_csv(eval_root / "metrics_final.csv", _final_metric_rows(results))
    write_json(eval_root / "eval_manifest.json", {"patches": results, "target_image_source": target_image_source})
    failed = [result for result in results if result.get("status") != "complete"]
    if failed:
        patch_ids = ", ".join(str(result.get("patch_id")) for result in failed)
        raise RuntimeError(f"splat.eval failed for patch(es): {patch_ids}")
    return results


def _next_eval_attempt_dir(patch_eval_dir: Path) -> Path:
    """Return a fresh eval attempt directory for a patch."""
    index = 1
    while (patch_eval_dir / f"attempt_{index}").exists():
        index += 1
    return patch_eval_dir / f"attempt_{index}"


def _final_metric_rows(results: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for result in results:
        metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
        assert isinstance(metrics, dict)
        rows.append(
            {
                "patch_id": result["patch_id"],
                "status": result["status"],
                "iteration": metrics.get("iteration", ""),
                "psnr": metrics.get("psnr", ""),
                "ssim": metrics.get("ssim", ""),
                "lpips": metrics.get("lpips", ""),
                "metric_source": metrics.get("metric_source", ""),
                **_status_eval_target_fields(result),
                "time_per_image": metrics.get("time_per_image", ""),
                "num_gaussians": metrics.get("num_gaussians", ""),
                "metrics_path": result["metrics_path"],
            }
        )
    return rows


def _eval_dataset_fields(manifest_path: Path) -> dict[str, object]:
    """Return eval target source and a representative holdout image size."""
    if not manifest_path.exists():
        return {"eval_target_source": "", "eval_image_width": "", "eval_image_height": ""}
    try:
        data = read_json(manifest_path)
    except (OSError, ValueError):
        return {"eval_target_source": "", "eval_image_width": "", "eval_image_height": ""}
    dimensions = data.get("holdout_image_dimensions")
    if isinstance(dimensions, dict):
        first = next((value for value in dimensions.values() if isinstance(value, dict)), {})
    else:
        first = dimensions[0] if isinstance(dimensions, list) and dimensions else {}
    first = first if isinstance(first, dict) else {}
    return {
        "eval_target_source": data.get("target_image_source", ""),
        "eval_image_width": first.get("width", ""),
        "eval_image_height": first.get("height", ""),
    }


def _status_eval_target_fields(result: dict[str, object]) -> dict[str, object]:
    """Return eval target fields embedded in a patch eval status row."""
    fields = result.get("eval_target")
    if isinstance(fields, dict):
        return {
            "eval_target_source": fields.get("eval_target_source", ""),
            "eval_image_width": fields.get("eval_image_width", ""),
            "eval_image_height": fields.get("eval_image_height", ""),
        }
    return {"eval_target_source": "", "eval_image_width": "", "eval_image_height": ""}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write a small CSV with fields from all rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        if not fields:
            return
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
