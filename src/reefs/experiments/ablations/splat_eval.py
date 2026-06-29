"""Serial LFS evaluation for SfM ablation runs."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from reefs.config.loader import load_config
from reefs.experiments.ablations.config import AblationConfig
from reefs.experiments.ablations.grid import SfMJob, select_even_patch_ids
from reefs.experiments.ablations.holdout import build_eval_dataset, load_or_create_holdout
from reefs.experiments.ablations.ledger import SPLAT_FIELDS, completed_job_ids, read_rows, upsert_row
from reefs.experiments.ablations.metrics import file_size, parse_lfs_metrics_csv, ply_vertex_count
from reefs.experiments.ablations.report import write_progress_markdown
from reefs.experiments.ablations.resource import ResourceSampler
from reefs.experiments.ablations.time_utils import utc_now
from reefs.io.yaml_json import write_json
from reefs.lfs.commands import build_lfs_train_command
from reefs.lfs.runner import _canonicalise_finished_output, _write_loss_history
from reefs.lfs.status import classify_lfs_status, parse_lfs_progress_lines
from reefs.splat.pipeline import RETRYABLE_LFS_WIDTH_SIGNATURES


@dataclass(frozen=True)
class PatchEval:
    """One patch eval task."""

    job: SfMJob
    patch_dir: Path
    patch_id: str
    row_id: str
    output_dir: Path
    eval_dataset_dir: Path
    holdout_path: Path


def run_splat_eval_phase(
    *,
    config: AblationConfig,
    jobs: list[SfMJob],
    ensure_patches,
    force_jobs: set[str],
) -> None:
    """Train all patches for each SfM job, serially and resumably."""
    _backup_ledgers(config.output_root)
    results_path = config.output_root / "results_splat.csv"
    completed = completed_job_ids(results_path) - force_jobs
    jobs = _clean_sfm_jobs(config=config, jobs=jobs)
    for job in jobs:
        ensure_patches(job)
    patch_ids_by_job = _patch_ids_by_job(config=config, jobs=jobs)
    _write_splat_eval_summary(config=config, jobs=jobs, patch_ids_by_job=patch_ids_by_job)
    for job in jobs:
        for task in _patch_tasks(config=config, job=job, patch_ids=patch_ids_by_job[job.job_id]):
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


def _patch_ids_by_job(*, config: AblationConfig, jobs: list[SfMJob]) -> dict[str, list[str]]:
    """Select evenly spaced validation patches independently per SfM job."""
    selected: dict[str, list[str]] = {}
    for job in jobs:
        patches_dir = job.dataset.project_dir / "runs" / job.job_id / "splat" / "patches"
        available = {path.name for path in patches_dir.iterdir() if path.is_dir()}
        if not available:
            raise FileNotFoundError(f"missing patch outputs: {patches_dir}")
        selected_ids = select_even_patch_ids(sorted(available), config.validation_patch_count)
        if len(selected_ids) < config.validation_patch_count:
            raise ValueError(f"only {len(selected_ids)} patches available for {job.job_id}")
        selected[job.job_id] = selected_ids
    return selected


def _patch_ids_by_dataset(*, config: AblationConfig, jobs: list[SfMJob]) -> dict[str, list[str]]:
    """Compatibility view of per-job patch selection for tests and scripts."""
    return _patch_ids_by_job(config=config, jobs=jobs)


def _patch_tasks(*, config: AblationConfig, job: SfMJob, patch_ids: list[str]) -> list[PatchEval]:
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
                holdout_path=config.output_root
                / "holdouts"
                / job.dataset.name
                / job.job_id
                / f"patch{config.default_patch_size}"
                / f"{patch_id}.json",
            )
        )
    return tasks


def _run_patch(*, config: AblationConfig, task: PatchEval) -> dict[str, object]:
    pipeline_config = load_config(task.job.dataset.config)
    train = pipeline_config.advanced.splat.train
    holdout = load_or_create_holdout(
        patch_dir=task.patch_dir,
        canonical_path=task.holdout_path,
        holdout_fraction=config.holdout_fraction,
    )
    if holdout.missing_holdout_images:
        missing = ", ".join(holdout.missing_holdout_images)
        raise ValueError(f"canonical holdout images are missing for {task.row_id}: {missing}")
    build_eval_dataset(patch_dir=task.patch_dir, output_dir=task.eval_dataset_dir, holdout=holdout)
    widths = [train.max_width, *train.retry_max_width]
    attempts: list[dict[str, object]] = []
    for index, max_width in enumerate(widths):
        attempt_dir = _next_attempt_dir(task.output_dir)
        attempt_dir.mkdir(parents=True, exist_ok=True)
        command = build_lfs_train_command(
            lfs_bin=pipeline_config.tools.lfs_bin,
            patch_id=task.patch_id,
            dataset_dir=task.eval_dataset_dir,
            output_dir=attempt_dir,
            num_iters=train.num_iters,
            num_splats_per_patch=config.default_splat_count,
            strategy=train.strategy,
            headless=train.headless,
            max_width=max_width,
            lfs_config=train.lfs_config,
            eval_enabled=True,
            test_every=holdout.test_every,
        )
        log_path = attempt_dir / "run.log"
        start = perf_counter()
        with ResourceSampler(attempt_dir / "resource_samples.csv", interval_seconds=15) as sampler:
            with log_path.open("w", encoding="utf-8") as log:
                log.write(f"## {task.row_id} | {utc_now()}\n$ {' '.join(command.args)}\n")
                log.flush()
                completed = subprocess.run(
                    command.args,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False,
                )
        duration = round(perf_counter() - start, 3)
        resource = sampler.summary()
        row = _finish_patch(
            task=task,
            attempt_dir=attempt_dir,
            log_path=log_path,
            return_code=completed.returncode,
            duration=duration,
            resource=resource,
            train=train,
            max_width=max_width,
            holdout_path=task.holdout_path,
            eval_dataset_dir=task.eval_dataset_dir,
        )
        attempts.append({"max_width": max_width, "status": row["status"], "failure_reason": row["failure_reason"]})
        if str(row["status"]).startswith("complete"):
            row["attempts"] = attempts
            return row
        if index == len(widths) - 1 or not _is_retryable_width_failure(row, log_path):
            row["attempts"] = attempts
            return row
    raise RuntimeError("unreachable LFS retry state")


def _finish_patch(
    *,
    task: PatchEval,
    attempt_dir: Path,
    log_path: Path,
    return_code: int,
    duration: float,
    resource,
    train,
    max_width: int | None,
    holdout_path: Path,
    eval_dataset_dir: Path,
) -> dict[str, object]:
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    progress = parse_lfs_progress_lines(lines)
    _write_loss_history(attempt_dir / "loss_history.csv", progress)
    status = classify_lfs_status(
        patch_id=task.patch_id,
        requested_iterations=train.num_iters,
        return_code=return_code,
        output_dir=attempt_dir,
        progress=progress,
        severe_completion_threshold=train.severe_completion_threshold,
    )
    status = _canonicalise_finished_output(status, attempt_dir)
    metrics = parse_lfs_metrics_csv(attempt_dir / "metrics.csv")
    output_file = Path(str(status["output_file"])) if status.get("output_file") else attempt_dir / "splat_finished.ply"
    row = {
        "job_id": task.row_id,
        "dataset": task.job.dataset.name,
        "variant": task.job.variant.name,
        "patch_id": task.patch_id,
        "patch_size": task.job.patch_size,
        "splat_count": task.job.splat_count,
        "max_width": max_width or "",
        "status": status["status"],
        "ssim": metrics.get("ssim", ""),
        "psnr": metrics.get("psnr", ""),
        "training_runtime_seconds": duration,
        "output_ply_size_bytes": file_size(output_file) or "",
        "output_sog_size_bytes": "",
        "actual_splat_count": metrics.get("num_gaussians") or ply_vertex_count(output_file) or "",
        "peak_ram_mib": resource.peak_ram_mib or "",
        "peak_vram_mib": resource.peak_vram_mib or "",
        "failure_reason": status.get("reason", ""),
        "updated_at": utc_now(),
    }
    write_json(
        attempt_dir / "training_status.json",
        {
            **status,
            "duration_seconds": duration,
            "metrics": metrics,
            "holdout": str(holdout_path),
            "eval_dataset": str(eval_dataset_dir),
            "row": row,
        },
    )
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[exit_code] {return_code}\n[duration_seconds] {duration}\n")
    return row


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
    for name in ["manifest.csv", "results_sfm.csv", "results_splat.csv", "results_final.csv"]:
        source = output_root / name
        if source.exists():
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, backup_dir / name)


def _write_splat_eval_summary(
    *,
    config: AblationConfig,
    jobs: list[SfMJob],
    patch_ids_by_job: dict[str, list[str]],
) -> None:
    rows = {row.get("job_id", ""): row for row in read_rows(config.output_root / "results_splat.csv")}
    payload = {
        "note": "Patch IDs and held-out images are selected per SfM run; they are not shared across variants.",
        "expected_rows": len(jobs) * config.validation_patch_count,
        "jobs": [
            {
                "job_id": job.job_id,
                "dataset": job.dataset.name,
                "variant": job.variant.name,
                "selected_patch_ids": patch_ids_by_job[job.job_id],
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
        "",
        "| job | dataset | variant | patch | status | SSIM | PSNR | runtime s |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for job in jobs:
        for patch_id in patch_ids_by_job[job.job_id]:
            row = rows.get(f"splat_eval_{job.job_id}_{patch_id}", {})
            lines.append(
                f"| `{job.job_id}` | {job.dataset.name} | {job.variant.name} | {patch_id} | "
                f"{row.get('status', 'pending')} | {row.get('ssim', '')} | {row.get('psnr', '')} | "
                f"{row.get('training_runtime_seconds', '')} |"
            )
    (config.output_root / "splat_eval_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
