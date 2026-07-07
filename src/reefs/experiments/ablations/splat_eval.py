"""Serial LFS evaluation for SfM ablation runs."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from reefs.config.loader import load_config
from reefs.experiments.ablations.config import AblationConfig
from reefs.experiments.ablations.grid import SfMJob, SplatJob, select_even_patch_ids
from reefs.experiments.ablations.ledger import (
    METRICS_LONG_FIELDS,
    SPLAT_FIELDS,
    atomic_write_csv,
    completed_job_ids,
    read_rows,
    upsert_row,
)
from reefs.experiments.ablations.metrics import file_size, ply_vertex_count
from reefs.experiments.ablations.report import write_progress_markdown
from reefs.experiments.ablations.resource import ResourceSampler
from reefs.experiments.ablations.time_utils import utc_now
from reefs.eval.holdout import build_eval_dataset, load_or_create_holdout, normalise_target_image_source
from reefs.io.yaml_json import write_json
from reefs.eval.lfs import LfsEvalAttemptResult, bounded_eval_steps, run_lfs_eval_attempt
from reefs.splat.pipeline import RETRYABLE_LFS_WIDTH_SIGNATURES


@dataclass(frozen=True)
class PatchEval:
    """One patch eval task."""

    job: SfMJob | SplatJob
    patch_dir: Path
    patch_id: str
    row_id: str
    output_dir: Path
    eval_dataset_dir: Path
    holdout_path: Path
    train_iters: int | None = None


def run_splat_eval_phase(
    *,
    config: AblationConfig,
    jobs: list[SfMJob | SplatJob],
    ensure_patches,
    force_jobs: set[str],
    require_clean_sfm: bool = True,
    train_iters: int | None = None,
) -> None:
    """Train all patches for each SfM job, serially and resumably."""
    _backup_ledgers(config.output_root)
    results_path = config.output_root / "results_splat.csv"
    completed = completed_job_ids(results_path) - force_jobs
    if require_clean_sfm:
        jobs = _clean_sfm_jobs(config=config, jobs=jobs)
    for job in jobs:
        ensure_patches(job)
    patch_ids_by_job = _patch_ids_by_job(config=config, jobs=jobs)
    _write_splat_eval_summary(config=config, jobs=jobs, patch_ids_by_job=patch_ids_by_job)
    for job in jobs:
        for task in _patch_tasks(
            config=config,
            job=job,
            patch_ids=patch_ids_by_job[job.job_id],
            train_iters=train_iters,
        ):
            if task.row_id in completed:
                continue
            row = _run_patch(config=config, task=task)
            upsert_row(results_path, SPLAT_FIELDS, row)
            write_json(task.output_dir / "latest_status.json", row)
            if str(row["status"]).startswith("complete"):
                completed.add(task.row_id)
            write_progress_markdown(config.output_root)
            _write_splat_eval_summary(config=config, jobs=jobs, patch_ids_by_job=patch_ids_by_job)


def _clean_sfm_jobs(*, config: AblationConfig, jobs: list[SfMJob]) -> list[SfMJob]:
    successful = {
        row["job_id"]
        for row in read_rows(config.output_root / "results_sfm.csv")
        if row.get("status") == "complete"
    }
    return [job for job in jobs if job.job_id in successful]


def _patch_ids_by_job(*, config: AblationConfig, jobs: list[SfMJob | SplatJob]) -> dict[str, list[str]]:
    """Select evenly spaced validation patches independently per SfM job."""
    selected: dict[str, list[str]] = {}
    for job in jobs:
        patches_dir = job.dataset.project_dir / "runs" / job.job_id / "splat" / "patches"
        available = {path.name for path in patches_dir.iterdir() if path.is_dir()}
        if not available:
            raise FileNotFoundError(f"missing patch outputs: {patches_dir}")
        selected_ids = select_even_patch_ids(sorted(available), config.validation_patch_count)
        selected[job.job_id] = selected_ids
    return selected


def _patch_ids_by_dataset(*, config: AblationConfig, jobs: list[SfMJob]) -> dict[str, list[str]]:
    """Compatibility view of per-job patch selection for tests and scripts."""
    return _patch_ids_by_job(config=config, jobs=jobs)


def _patch_tasks(
    *,
    config: AblationConfig,
    job: SfMJob | SplatJob,
    patch_ids: list[str],
    train_iters: int | None = None,
) -> list[PatchEval]:
    patches_dir = job.dataset.project_dir / "runs" / job.job_id / "splat" / "patches"
    if not patches_dir.exists():
        raise FileNotFoundError(f"missing patch directory: {patches_dir}")
    tasks: list[PatchEval] = []
    for patch_id in patch_ids:
        patch_dir = patches_dir / patch_id
        if not patch_dir.is_dir():
            raise FileNotFoundError(f"missing selected patch directory: {patch_dir}")
        row_id = f"splat_eval_{job.job_id}_{patch_id}"
        tasks.append(
            PatchEval(
                job=job,
                patch_dir=patch_dir,
                patch_id=patch_id,
                row_id=row_id,
                output_dir=config.output_root / "splat_eval" / job.job_id / patch_id,
                eval_dataset_dir=config.output_root / "eval_datasets" / job.job_id / patch_id,
                holdout_path=_holdout_path(config=config, job=job, patch_id=patch_id),
                train_iters=train_iters,
            )
        )
    return tasks


def _holdout_path(*, config: AblationConfig, job: SfMJob | SplatJob, patch_id: str) -> Path:
    """Return the canonical holdout path for Stage 1 or comparable Stage 2 jobs."""
    if isinstance(job, SplatJob):
        return (
            config.output_root
            / "holdouts"
            / job.dataset.name
            / "stage2"
            / job.sfm_variant
            / f"patch{job.patch_size}"
            / patch_id
            / "holdout.json"
        )
    return (
        config.output_root
        / "holdouts"
        / job.dataset.name
        / job.job_id
        / f"patch{job.patch_size}"
        / f"{patch_id}.json"
    )


def _run_patch(*, config: AblationConfig, task: PatchEval) -> dict[str, object]:
    pipeline_config = load_config(task.job.dataset.config)
    train = pipeline_config.advanced.splat.train
    eval_config = pipeline_config.advanced.eval
    holdout = load_or_create_holdout(
        patch_dir=task.patch_dir,
        canonical_path=task.holdout_path,
        holdout_fraction=config.holdout_fraction,
    )
    if holdout.missing_holdout_images:
        missing = ", ".join(holdout.missing_holdout_images)
        raise ValueError(f"canonical holdout images are missing for {task.row_id}: {missing}")
    full_res_images_dir = None
    target_image_source = normalise_target_image_source(config.validation_target_image_source)
    if target_image_source == "full_resolution_undistorted":
        full_res_images_dir = config.validation_full_resolution_undistorted_images_dir
        if full_res_images_dir is None:
            full_res_images_dir = task.patch_dir.parents[2] / "sfm" / "undistorted_full_resolution" / "images"
    build_eval_dataset(
        patch_dir=task.patch_dir,
        output_dir=task.eval_dataset_dir,
        holdout=holdout,
        target_image_source=target_image_source,
        source_images_dir=full_res_images_dir,
    )
    widths = [None] if target_image_source == "full_resolution_undistorted" else [train.max_width, *train.retry_max_width]
    attempts: list[dict[str, object]] = []
    for index, max_width in enumerate(widths):
        attempt_dir = _next_attempt_dir(task.output_dir)
        attempt_dir.mkdir(parents=True, exist_ok=True)
        with ResourceSampler(attempt_dir / "resource_samples.csv", interval_seconds=15) as sampler:
            attempt = run_lfs_eval_attempt(
                lfs_bin=pipeline_config.tools.lfs_bin,
                patch_id=task.patch_id,
                dataset_dir=task.eval_dataset_dir,
                output_dir=attempt_dir,
                num_iters=task.train_iters or train.num_iters,
                num_splats_per_patch=task.job.splat_count,
                strategy=train.strategy,
                headless=train.headless,
                max_width=max_width,
                base_lfs_config=train.lfs_config,
                eval_steps=eval_config.eval_steps,
                test_every=holdout.test_every,
                severe_completion_threshold=train.severe_completion_threshold,
                compute_lpips="lpips" in eval_config.metrics,
            )
        resource = sampler.summary()
        row = _finish_patch(
            task=task,
            attempt_dir=attempt_dir,
            attempt=attempt,
            resource=resource,
            max_width=max_width,
            holdout_path=task.holdout_path,
            eval_dataset_dir=task.eval_dataset_dir,
        )
        attempts.append({"max_width": max_width, "status": row["status"], "failure_reason": row["failure_reason"]})
        if str(row["status"]).startswith("complete"):
            row["attempts"] = attempts
            return row
        if index == len(widths) - 1 or not _is_retryable_width_failure(row, attempt.log_path):
            row["attempts"] = attempts
            return row
    raise RuntimeError("unreachable LFS retry state")


def _bounded_steps(steps: list[int], max_iteration: int) -> list[int]:
    """Keep explicit LFS eval/save steps within the requested training horizon."""
    return bounded_eval_steps(steps, max_iteration)


def _finish_patch(
    *,
    task: PatchEval,
    attempt_dir: Path,
    attempt: LfsEvalAttemptResult,
    resource,
    max_width: int | None,
    holdout_path: Path,
    eval_dataset_dir: Path,
) -> dict[str, object]:
    eval_target = _eval_target_fields(eval_dataset_dir / "eval_dataset_manifest.json")
    _upsert_metrics_long(
        path=task.output_dir.parents[2] / "metrics_long.csv",
        task=task,
        attempt_dir=attempt_dir,
        metrics_path=attempt.metrics_path,
        rows=attempt.metric_rows,
        max_width=max_width,
        eval_target=eval_target,
    )
    output_file = (
        Path(str(attempt.status["output_file"]))
        if attempt.status.get("output_file")
        else attempt_dir / "splat_finished.ply"
    )
    row = {
        "job_id": task.row_id,
        "dataset": task.job.dataset.name,
        "variant": _job_variant(task.job),
        "patch_id": task.patch_id,
        "patch_size": task.job.patch_size,
        "splat_count": task.job.splat_count,
        "max_width": max_width or "",
        "status": attempt.status["status"],
        "ssim": attempt.metrics.get("ssim", ""),
        "psnr": attempt.metrics.get("psnr", ""),
        "lpips": attempt.metrics.get("lpips", ""),
        "metric_source": attempt.metrics.get("metric_source", ""),
        **eval_target,
        "training_runtime_seconds": round(attempt.duration_seconds, 3),
        "output_ply_size_bytes": file_size(output_file) or "",
        "output_sog_size_bytes": "",
        "actual_splat_count": attempt.metrics.get("num_gaussians") or ply_vertex_count(output_file) or "",
        "peak_ram_mib": resource.peak_ram_mib or "",
        "peak_vram_mib": resource.peak_vram_mib or "",
        "failure_reason": attempt.status.get("reason", ""),
        "updated_at": utc_now(),
    }
    write_json(
        attempt_dir / "training_status.json",
        {
            **attempt.status,
            "duration_seconds": attempt.duration_seconds,
            "metrics": attempt.metrics,
            "holdout": str(holdout_path),
            "eval_dataset": str(eval_dataset_dir),
            "eval_dataset_manifest": str(eval_dataset_dir / "eval_dataset_manifest.json"),
            "row": row,
        },
    )
    return row


def _eval_target_fields(manifest_path: Path) -> dict[str, object]:
    """Return eval target source and dimensions for result ledgers."""
    if not manifest_path.exists():
        return {"eval_target_source": "", "eval_image_width": "", "eval_image_height": ""}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
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


def _upsert_metrics_long(
    *,
    path: Path,
    task: PatchEval,
    attempt_dir: Path,
    metrics_path: Path,
    rows: list[dict[str, float | int]],
    max_width: int | None,
    eval_target: dict[str, object],
) -> None:
    """Merge per-iteration LFS eval metrics for one patch attempt."""
    if not rows:
        return
    existing = read_rows(path)
    attempt = attempt_dir.name
    prefix = (task.row_id, attempt)
    kept = [row for row in existing if (row.get("job_id"), row.get("attempt")) != prefix]
    now = utc_now()
    new_rows = []
    for row in rows:
        new_rows.append(
            {
                "job_id": task.row_id,
                "dataset": task.job.dataset.name,
                "variant": _job_variant(task.job),
                "patch_id": task.patch_id,
                "patch_size": task.job.patch_size,
                "splat_count": task.job.splat_count,
                "max_width": max_width or "",
                "attempt": attempt,
                "iteration": row["iteration"],
                "psnr": row["psnr"],
                "ssim": row["ssim"],
                "lpips": row.get("lpips", ""),
                "metric_source": row.get("metric_source", ""),
                **eval_target,
                "time_per_image": row.get("time_per_image", ""),
                "num_gaussians": row.get("num_gaussians", ""),
                "metrics_path": str(metrics_path),
                "updated_at": now,
            }
        )
    atomic_write_csv(path, METRICS_LONG_FIELDS, [*kept, *new_rows])


def _is_retryable_width_failure(row: dict[str, object], log_path: Path) -> bool:
    if row.get("status") not in {"failed", "severe_warning"}:
        return False
    text = log_path.read_text(encoding="utf-8", errors="replace").lower()
    return any(signature in text for signature in RETRYABLE_LFS_WIDTH_SIGNATURES)


def _next_attempt_dir(output_dir: Path) -> Path:
    index = 1
    while (output_dir / f"attempt_{index}").exists():
        index += 1
    return output_dir / f"attempt_{index}"


def _backup_ledgers(output_root: Path) -> None:
    backup_dir = output_root / "backups" / utc_now().replace(":", "")
    for name in ["manifest.csv", "results_sfm.csv", "results_splat.csv", "metrics_long.csv", "results_final.csv"]:
        source = output_root / name
        if source.exists():
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, backup_dir / name)


def _write_splat_eval_summary(
    *,
    config: AblationConfig,
    jobs: list[SfMJob | SplatJob],
    patch_ids_by_job: dict[str, list[str]],
) -> None:
    rows = {row.get("job_id", ""): row for row in read_rows(config.output_root / "results_splat.csv")}
    expected_rows = sum(len(patch_ids_by_job[job.job_id]) for job in jobs)
    payload = {
        "note": _selection_note(jobs),
        "requested_patches_per_job": config.validation_patch_count,
        "expected_rows": expected_rows,
        "jobs": [
            {
                "job_id": job.job_id,
                "dataset": job.dataset.name,
                "variant": _job_variant(job),
                "selected_patch_ids": patch_ids_by_job[job.job_id],
                "selected_patch_count": len(patch_ids_by_job[job.job_id]),
            }
            for job in jobs
        ],
    }
    write_json(config.output_root / "splat_eval_selection.json", payload)
    lines = [
        "# Splat Eval Summary",
        "",
        "Patch IDs and held-out images are selected per SfM run; they are not shared across variants.",
        "",
        f"Expected rows: {payload['expected_rows']}",
        f"Requested patches per job: {payload['requested_patches_per_job']}",
        "",
        "| job | dataset | variant | patch | status | SSIM | PSNR | runtime s |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for job in jobs:
        for patch_id in patch_ids_by_job[job.job_id]:
            row = rows.get(f"splat_eval_{job.job_id}_{patch_id}", {})
            lines.append(
                f"| `{job.job_id}` | {job.dataset.name} | {_job_variant(job)} | {patch_id} | "
                f"{row.get('status', 'pending')} | {row.get('ssim', '')} | {row.get('psnr', '')} | "
                f"{row.get('training_runtime_seconds', '')} |"
            )
    (config.output_root / "splat_eval_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _selection_note(jobs: list[SfMJob | SplatJob]) -> str:
    """Describe holdout comparability for the selected job set."""
    if jobs and all(isinstance(job, SplatJob) for job in jobs):
        return (
            "Stage 2 patch IDs and held-out images are shared across comparable splat variants "
            "with the same dataset, SfM source label, patch size, patch id, and patch image set."
        )
    return "Stage 1 patch IDs and held-out images are selected per SfM job; they are not shared across variants."


def _job_variant(job: SfMJob | SplatJob) -> str:
    return job.variant.name if isinstance(job, SfMJob) else job.sfm_variant
