"""Shared LFS evaluation attempt runner."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from reefs.experiments.ablations.metrics import parse_lfs_metrics_csv, parse_lfs_metrics_rows
from reefs.eval.lpips import add_lpips_to_lfs_metrics
from reefs.io.yaml_json import write_json
from reefs.lfs.commands import build_lfs_train_command, write_lfs_eval_config
from reefs.lfs.runner import _canonicalise_finished_output, _write_loss_history
from reefs.lfs.status import classify_lfs_status, parse_lfs_progress_lines


@dataclass(frozen=True)
class LfsEvalAttemptResult:
    """Result from one LFS eval attempt."""

    status: dict[str, object]
    metrics: dict[str, float | int]
    metric_rows: list[dict[str, float | int]]
    duration_seconds: float
    return_code: int
    log_path: Path
    metrics_path: Path
    lfs_config: Path


def bounded_eval_steps(steps: list[int], max_iteration: int) -> list[int]:
    """Keep eval/save steps inside the requested training horizon."""
    bounded = [step for step in steps if step <= max_iteration]
    if max_iteration not in bounded:
        bounded.append(max_iteration)
    return sorted(set(bounded))


def run_lfs_eval_attempt(
    *,
    lfs_bin: str,
    patch_id: str,
    dataset_dir: Path,
    output_dir: Path,
    num_iters: int,
    num_splats_per_patch: int,
    strategy: str,
    headless: bool,
    max_width: int | None,
    base_lfs_config: str | None,
    eval_steps: list[int],
    test_every: int,
    severe_completion_threshold: float,
    compute_lpips: bool = False,
) -> LfsEvalAttemptResult:
    """Run one LFS training command in eval mode and parse its outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    lfs_config = write_lfs_eval_config(
        path=output_dir / "lfs_eval_config.json",
        base_config=base_lfs_config,
        eval_steps=bounded_eval_steps(eval_steps, num_iters),
        save_steps=bounded_eval_steps(eval_steps, num_iters),
        headless=headless,
        eval_enabled=True,
        save_eval_images=compute_lpips,
    )
    command = build_lfs_train_command(
        lfs_bin=lfs_bin,
        patch_id=patch_id,
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        num_iters=num_iters,
        num_splats_per_patch=num_splats_per_patch,
        strategy=strategy,
        headless=headless,
        max_width=max_width,
        lfs_config=lfs_config,
        eval_enabled=True,
        test_every=test_every,
        save_eval_images=compute_lpips,
    )
    log_path = output_dir / "run.log"
    start = perf_counter()
    with log_path.open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(command.args) + "\n\n")
        log.flush()
        completed = subprocess.run(command.args, stdout=log, stderr=subprocess.STDOUT, text=True, check=False)
    duration = round(perf_counter() - start, 6)
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    progress = parse_lfs_progress_lines(lines)
    _write_loss_history(output_dir / "loss_history.csv", progress)
    status = classify_lfs_status(
        patch_id=patch_id,
        requested_iterations=num_iters,
        return_code=completed.returncode,
        output_dir=output_dir,
        progress=progress,
        severe_completion_threshold=severe_completion_threshold,
    )
    status = _canonicalise_finished_output(status, output_dir)
    metrics_path = output_dir / "metrics.csv"
    metric_rows = parse_lfs_metrics_rows(metrics_path)
    if compute_lpips and metric_rows:
        lpips_values = add_lpips_to_lfs_metrics(
            output_dir=output_dir,
            metrics_path=metrics_path,
            iterations=[int(row["iteration"]) for row in metric_rows],
        )
        write_json(
            output_dir / "lpips_metrics.json",
            {
                "metric": "lpips",
                "implementation": "lpips.LPIPS(net='alex')",
                "source_images": "LichtFeld Studio eval_step_<iteration> GT/render comparison PNGs",
                "separator_px": 4,
                "values": lpips_values,
            },
        )
        metric_rows = parse_lfs_metrics_rows(metrics_path)
    metrics = parse_lfs_metrics_csv(metrics_path)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[exit_code] {completed.returncode}\n[duration_seconds] {duration}\n")
    return LfsEvalAttemptResult(
        status=status,
        metrics=metrics,
        metric_rows=metric_rows,
        duration_seconds=duration,
        return_code=completed.returncode,
        log_path=log_path,
        metrics_path=metrics_path,
        lfs_config=lfs_config,
    )
