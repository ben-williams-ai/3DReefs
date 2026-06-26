"""Parallel LFS evaluation for SfM ablation runs."""

from __future__ import annotations

import subprocess
import time
import shutil
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import TextIO

from reefs.config.loader import load_config
from reefs.experiments.ablations.config import AblationConfig
from reefs.experiments.ablations.grid import SfMJob
from reefs.experiments.ablations.holdout import build_eval_dataset, load_or_create_holdout
from reefs.experiments.ablations.ledger import SPLAT_FIELDS, completed_job_ids, upsert_row
from reefs.experiments.ablations.metrics import file_size, parse_lfs_metrics_csv, ply_vertex_count
from reefs.experiments.ablations.report import write_progress_markdown
from reefs.experiments.ablations.resource import ResourceSampler
from reefs.experiments.ablations.time_utils import utc_now
from reefs.io.yaml_json import write_json
from reefs.lfs.commands import build_lfs_train_command
from reefs.lfs.runner import _canonicalise_finished_output, _write_loss_history
from reefs.lfs.status import classify_lfs_status, parse_lfs_progress_lines


INITIAL_PARALLEL = 2
MAX_PARALLEL = 2
MIN_FREE_VRAM_MIB = 12_000
INCREASE_FREE_VRAM_MIB = 35_000


@dataclass
class PatchEval:
    """One patch eval task."""

    job: SfMJob
    patch_dir: Path
    patch_id: str
    row_id: str
    output_dir: Path
    eval_dataset_dir: Path
    holdout_path: Path


@dataclass
class ActivePatch:
    """One running LFS process."""

    task: PatchEval
    process: subprocess.Popen[str]
    log_path: Path
    log_handle: TextIO
    started: float
    sampler: ResourceSampler


def run_splat_eval_phase(
    *,
    config: AblationConfig,
    jobs: list[SfMJob],
    ensure_patches,
    force_jobs: set[str],
) -> None:
    """Run all-patch LFS eval for each SfM job, one probe at a time."""
    completed = completed_job_ids(config.output_root / "results_splat.csv") - force_jobs
    for job in jobs:
        ensure_patches(job)
        tasks = _patch_tasks(config=config, job=job)
        pending = [task for task in tasks if task.row_id not in completed]
        if not pending:
            continue
        _run_probe(config=config, job=job, pending=pending, completed=completed)
        write_progress_markdown(config.output_root)


def _patch_tasks(*, config: AblationConfig, job: SfMJob) -> list[PatchEval]:
    run_dir = job.dataset.project_dir / "runs" / job.job_id
    patches_dir = run_dir / "splat" / "patches"
    if not patches_dir.exists():
        raise FileNotFoundError(f"missing patch directory: {patches_dir}")
    tasks: list[PatchEval] = []
    for patch_dir in sorted(path for path in patches_dir.iterdir() if path.is_dir()):
        patch_id = patch_dir.name
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
                / f"patch{config.default_patch_size}"
                / f"{patch_id}.json",
            )
        )
    return tasks


def _run_probe(
    *,
    config: AblationConfig,
    job: SfMJob,
    pending: list[PatchEval],
    completed: set[str],
) -> None:
    pipeline_config = load_config(job.dataset.config)
    train = pipeline_config.advanced.splat.train
    target_parallel = INITIAL_PARALLEL
    capped_parallel = MAX_PARALLEL
    attempts: dict[str, int] = {}
    queue = list(pending)
    active: list[ActivePatch] = []
    duration_by_parallel: dict[int, list[float]] = {}
    probe_dir = config.output_root / "jobs" / job.job_id / "splat_eval"
    probe_dir.mkdir(parents=True, exist_ok=True)
    while queue or active:
        while queue and len(active) < target_parallel:
            task = queue.pop(0)
            attempts[task.row_id] = attempts.get(task.row_id, 0) + 1
            active.append(_start_patch(config=config, task=task, attempt=attempts[task.row_id], train=train))
        time.sleep(5)
        free_vram = _free_vram_mib()
        finished = [item for item in active if item.process.poll() is not None]
        for item in finished:
            active.remove(item)
            row = _finish_patch(config=config, item=item, train=train)
            upsert_row(config.output_root / "results_splat.csv", SPLAT_FIELDS, row)
            write_json(item.task.output_dir / "latest_status.json", row)
            if str(row["status"]).startswith("complete"):
                completed.add(item.task.row_id)
                duration_by_parallel.setdefault(target_parallel, []).append(float(row["training_runtime_seconds"]))
            elif attempts[item.task.row_id] < 2:
                target_parallel = max(1, target_parallel - 1)
                queue.insert(0, item.task)
            write_progress_markdown(config.output_root)
        if free_vram is not None and free_vram < MIN_FREE_VRAM_MIB:
            target_parallel = max(1, target_parallel - 1)
        elif (
            free_vram is not None
            and free_vram >= INCREASE_FREE_VRAM_MIB
            and target_parallel < capped_parallel
            and duration_by_parallel
        ):
            target_parallel += 1
        target_parallel = _trim_if_parallel_slower(target_parallel, duration_by_parallel)


def _start_patch(*, config: AblationConfig, task: PatchEval, attempt: int, train) -> ActivePatch:
    holdout = load_or_create_holdout(
        patch_dir=task.patch_dir,
        canonical_path=task.holdout_path,
        holdout_fraction=config.holdout_fraction,
    )
    build_eval_dataset(patch_dir=task.patch_dir, output_dir=task.eval_dataset_dir, holdout=holdout)
    attempt_dir = task.output_dir / f"attempt_{attempt}"
    if attempt_dir.exists():
        shutil.rmtree(attempt_dir)
    attempt_dir.mkdir(parents=True, exist_ok=True)
    command = build_lfs_train_command(
        lfs_bin=load_config(task.job.dataset.config).tools.lfs_bin,
        patch_id=task.patch_id,
        dataset_dir=task.eval_dataset_dir,
        output_dir=attempt_dir,
        num_iters=train.num_iters,
        num_splats_per_patch=config.default_splat_count,
        strategy=train.strategy,
        headless=train.headless,
        max_width=train.max_width,
        lfs_config=train.lfs_config,
        eval_enabled=True,
        test_every=holdout.test_every,
    )
    log_path = attempt_dir / "run.log"
    log_handle = log_path.open("w", encoding="utf-8")
    log_handle.write(f"## {task.row_id} attempt {attempt} | {utc_now()}\n$ {' '.join(command.args)}\n")
    log_handle.flush()
    process = subprocess.Popen(
        command.args,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    sampler = ResourceSampler(attempt_dir / "resource_samples.csv", interval_seconds=15)
    sampler.__enter__()
    return ActivePatch(
        task=task,
        process=process,
        log_path=log_path,
        log_handle=log_handle,
        started=perf_counter(),
        sampler=sampler,
    )


def _finish_patch(*, config: AblationConfig, item: ActivePatch, train) -> dict[str, object]:
    return_code = item.process.wait()
    item.log_handle.close()
    duration = round(perf_counter() - item.started, 3)
    resource = item.sampler.stop()
    lines = item.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    progress = parse_lfs_progress_lines(lines)
    _write_loss_history(item.log_path.parent / "loss_history.csv", progress)
    status = classify_lfs_status(
        patch_id=item.task.patch_id,
        requested_iterations=train.num_iters,
        return_code=return_code,
        output_dir=item.log_path.parent,
        progress=progress,
        severe_completion_threshold=train.severe_completion_threshold,
    )
    status = _canonicalise_finished_output(status, item.log_path.parent)
    metrics = parse_lfs_metrics_csv(item.log_path.parent / "metrics.csv")
    output_file = Path(str(status["output_file"])) if status.get("output_file") else item.log_path.parent / "splat_finished.ply"
    row = {
        "job_id": item.task.row_id,
        "dataset": item.task.job.dataset.name,
        "variant": item.task.job.variant.name,
        "patch_id": item.task.patch_id,
        "patch_size": config.default_patch_size,
        "splat_count": config.default_splat_count,
        "max_width": train.max_width or "",
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
        item.log_path.parent / "training_status.json",
        {
            **status,
            "duration_seconds": duration,
            "metrics": metrics,
            "holdout": str(item.task.holdout_path),
            "eval_dataset": str(item.task.eval_dataset_dir),
            "row": row,
        },
    )
    with item.log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[exit_code] {return_code}\n[duration_seconds] {duration}\n")
    return row


def _free_vram_mib() -> int | None:
    completed = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=5,
    )
    if completed.returncode != 0:
        return None
    values = [int(line.strip()) for line in completed.stdout.splitlines() if line.strip().isdigit()]
    return min(values) if values else None


def _trim_if_parallel_slower(target: int, durations: dict[int, list[float]]) -> int:
    if target <= 1 or target not in durations or len(durations[target]) < 2:
        return target
    previous = max((value for value in durations if value < target and len(durations[value]) >= 2), default=None)
    if previous is None:
        return target
    current_rate = target / (sum(durations[target]) / len(durations[target]))
    previous_rate = previous / (sum(durations[previous]) / len(durations[previous]))
    return previous if current_rate < previous_rate * 1.05 else target
