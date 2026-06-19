"""Weekend experimental sweep runner.

Run with:
    PYTHONPATH=src uv run python -m sweep.run_sweep smoke
    PYTHONPATH=src uv run python -m sweep.run_sweep run
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from reefs.config.loader import load_config
from reefs.io.yaml_json import write_yaml

from sweep.holdout import build_eval_dataset, write_holdout_manifest
from sweep.metrics import (
    parse_lfs_log_metrics,
    parse_lfs_metrics_csv,
    psnr,
    ssim,
    summarise_lfs_log_loss,
    summarise_loss_history,
)


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "data" / "experiments"
PATCH_IDS = ["p000", "p001", "p002"]
PATCH_SIZES = [200, 400, 800]
SPLAT_COUNTS = [1_000_000, 2_000_000, 3_000_000]
DATASETS = {
    "dataset1": ROOT / "configs" / "datasets" / "dataset_01.yml",
    "dataset2": ROOT / "configs" / "datasets" / "dataset_02.yml",
}
COLMAP_VARIANTS = {
    "baseline": {},
    "focal_refine": {"advanced.sfm.intrinsics.refine.focal_length": True},
    "radial_focal": {
        "advanced.sfm.intrinsics.camera_model": "RADIAL",
        "advanced.sfm.intrinsics.refine.focal_length": True,
    },
    "matching_affine": {
        "advanced.sfm.intrinsics.refine.focal_length": True,
        "advanced.sfm.matching.sequential.overlap": 30,
        "advanced.sfm.matching.vocab_tree.num_images": 300,
        "advanced.sfm.feature_extraction.sift.estimate_affine_shape": True,
    },
    "incremental_focal": {
        "advanced.sfm.intrinsics.refine.focal_length": True,
        "advanced.sfm.reconstruction.backend": "incremental",
    },
}
RESULT_FIELDS = [
    "experiment_id",
    "group",
    "dataset",
    "colmap_variant",
    "patch_size",
    "splat_count",
    "patch_id",
    "status",
    "ssim",
    "psnr",
    "final_loss_last",
    "final_loss_ma20",
    "duration_seconds",
    "failure_reason",
    "updated_at",
]


@dataclass(frozen=True)
class Job:
    """One patch training/eval job."""

    group: str
    dataset: str
    colmap_variant: str
    patch_size: int
    splat_count: int
    patch_id: str

    @property
    def experiment_id(self) -> str:
        return (
            f"{self.group}_{self.dataset}_{self.colmap_variant}_"
            f"patch{self.patch_size}_{self.splat_count // 1_000_000}m_{self.patch_id}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["smoke", "run", "manifest", "report"])
    args = parser.parse_args(argv)
    EXPERIMENTS.mkdir(parents=True, exist_ok=True)
    if args.command == "smoke":
        return smoke()
    if args.command == "manifest":
        write_manifest(build_jobs())
        update_readme()
        return 0
    if args.command == "report":
        update_readme()
        return 0
    return run()


def smoke() -> int:
    """Run cheap checks before the long sweep."""
    try:
        _metric_self_check()
        jobs = build_jobs()
        write_manifest(jobs)
        first_patch = _find_existing_patch("dataset1", 400, "p000")
        holdout = write_holdout_manifest(
            first_patch,
            EXPERIMENTS / "smoke" / "holdout_manifest.json",
        )
        if not holdout.holdout_images:
            raise ValueError("smoke holdout was empty")
        build_eval_dataset(
            patch_dir=first_patch,
            output_dir=EXPERIMENTS / "smoke" / "eval_dataset",
            holdout=holdout,
        )
        _lfs_eval_smoke()
        _write_status("smoke", "passed", "Metric and holdout smoke checks passed.")
        update_readme()
        return 0
    except Exception as exc:
        _write_status("smoke", "failed", str(exc))
        update_readme()
        return 1


def run() -> int:
    """Run the selected weekend sweep serially."""
    if smoke() != 0:
        return 1
    jobs = build_jobs()
    write_manifest(jobs)
    for job in jobs:
        if _result_for(job):
            continue
        try:
            row = run_job(job)
        except Exception as exc:
            row = _row(job, status="failed", failure_reason=str(exc))
        append_result(row)
        update_readme()
    update_readme()
    return 0


def build_jobs() -> list[Job]:
    """Return the planned sweep matrix."""
    jobs: list[Job] = []
    for dataset in DATASETS:
        for patch_size in PATCH_SIZES:
            for splat_count in SPLAT_COUNTS:
                for patch_id in PATCH_IDS:
                    jobs.append(Job("splat_grid", dataset, "baseline", patch_size, splat_count, patch_id))
    for variant in ["focal_refine", "radial_focal", "matching_affine", "incremental_focal"]:
        for dataset in DATASETS:
            for patch_id in PATCH_IDS:
                jobs.append(Job("colmap_pose", dataset, variant, 400, 2_000_000, patch_id))
    return jobs


def run_job(job: Job) -> dict[str, object]:
    """Run patch generation if needed, train one patch, and parse metrics."""
    started = datetime.now(timezone.utc)
    exp_dir = EXPERIMENTS / job.experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    patch_dir = ensure_patch(job)
    holdout = write_holdout_manifest(patch_dir, exp_dir / "holdout_manifest.json")
    eval_dataset = exp_dir / "eval_dataset"
    build_eval_dataset(patch_dir=patch_dir, output_dir=eval_dataset, holdout=holdout)
    train_dir = exp_dir / "splat"
    train_dir.mkdir(exist_ok=True)
    config = load_config(DATASETS[job.dataset])
    command = [
        config.tools.lfs_bin,
        "-d",
        str(eval_dataset),
        "-o",
        str(train_dir),
        "--headless",
        "--eval",
        "--test-every",
        str(holdout.test_every),
        "-i",
        str(config.advanced.splat.train.num_iters),
        "--max-cap",
        str(job.splat_count),
        "--strategy",
        config.advanced.splat.train.strategy,
    ]
    log_path = exp_dir / "lfs.log"
    _run_logged(command, log_path=log_path)
    loss = summarise_loss_history(train_dir / "loss_history.csv")
    if loss.loss_count == 0:
        loss = summarise_lfs_log_loss(log_path)
    metrics = parse_lfs_metrics_csv(train_dir / "metrics.csv") or parse_lfs_log_metrics(log_path)
    if "ssim" not in metrics or "psnr" not in metrics:
        raise ValueError("LFS completed but no PSNR/SSIM metrics were parsed")
    ended = datetime.now(timezone.utc)
    return _row(
        job,
        status="complete",
        ssim_value=metrics.get("ssim"),
        psnr_value=metrics.get("psnr"),
        final_loss_last=loss.final_loss_last,
        final_loss_ma20=loss.final_loss_ma20,
        duration_seconds=(ended - started).total_seconds(),
    )


def ensure_patch(job: Job) -> Path:
    """Return an existing/generated patch directory for this job."""
    if job.colmap_variant == "baseline":
        try:
            existing = _find_existing_patch(job.dataset, job.patch_size, job.patch_id)
            return existing
        except ValueError:
            pass
    run_id = f"sweep_{job.dataset}_{job.colmap_variant}_patch{job.patch_size}"
    project_dir = ROOT / "data" / job.dataset
    run_dir = project_dir / "runs" / run_id
    if (run_dir / "splat" / "patches" / job.patch_id / "patch_metadata.json").exists():
        return run_dir / "splat" / "patches" / job.patch_id
    source_config = load_config(DATASETS[job.dataset]).model_dump(mode="json")
    _apply_config_overrides(source_config, COLMAP_VARIANTS[job.colmap_variant])
    source_config["advanced"]["splat"]["patching"]["max_cameras"] = job.patch_size
    source_config["advanced"]["splat"]["patching"]["patch_ids"] = PATCH_IDS
    source_config["advanced"]["splat"]["train"]["patch_ids"] = PATCH_IDS
    config_path = EXPERIMENTS / f"{run_id}.yml"
    write_yaml(config_path, source_config)
    _prepare_named_run_dir(job=job, run_dir=run_dir)
    steps = "sfm,splat.patch" if job.colmap_variant != "baseline" else "splat.patch"
    command = [
        sys.executable,
        str(ROOT / "main.py"),
        "--config",
        str(config_path),
        "--project-dir",
        str(project_dir),
        "--steps",
        steps,
        "--resume-policy",
        "overwrite",
        "--run-id",
        run_id,
    ]
    _run_logged(command, log_path=EXPERIMENTS / f"{run_id}.log", env={"PYTHONPATH": str(ROOT / "src")})
    patch_dir = run_dir / "splat" / "patches" / job.patch_id
    if not (patch_dir / "patch_metadata.json").exists():
        raise ValueError(f"patch generation did not create {patch_dir}")
    return patch_dir


def _prepare_named_run_dir(*, job: Job, run_dir: Path) -> None:
    """Create enough run structure for the repo CLI to accept --run-id."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(exist_ok=True)
    if job.colmap_variant != "baseline":
        return
    target = run_dir / "sfm"
    if target.exists():
        return
    source = _find_source_sfm(job.dataset)
    target.symlink_to(source.resolve(), target_is_directory=True)


def _find_source_sfm(dataset: str) -> Path:
    """Return an existing completed SfM directory for baseline patch generation."""
    runs = ROOT / "data" / dataset / "runs"
    for candidate in sorted(runs.iterdir()):
        sfm = candidate / "sfm"
        if (sfm / "undistorted" / "images").exists() and (sfm / "undistorted" / "sparse").exists():
            return sfm
    raise ValueError(f"no completed SfM source found for {dataset}")


def update_readme() -> None:
    """Write the live experiment report."""
    rows = read_results()
    complete = [row for row in rows if row["status"] == "complete"]
    failed = [row for row in rows if row["status"] == "failed"]
    best = sorted(
        complete,
        key=lambda row: (
            _float_or_neg_inf(row.get("ssim")),
            _float_or_neg_inf(row.get("psnr")),
            -_float_or_inf(row.get("final_loss_ma20")),
        ),
        reverse=True,
    )[:10]
    lines = [
        "# 3DReefs Experimental Sweep",
        "",
        f"Updated: {_now()}",
        "",
        "## Plan",
        "",
        "- Deadline: Monday 2026-06-22 09:00 BST.",
        "- Datasets: dataset1, dataset2.",
        "- Patches: p000, p001, p002.",
        "- Baseline sweep: patch sizes 200/400/800 and splat caps 1m/2m/3m.",
        "- COLMAP sweep: focal_refine, radial_focal, matching_affine, incremental_focal at patch400/2m.",
        "",
        "## Progress",
        "",
        f"- Completed jobs: {len(complete)}",
        f"- Failed jobs: {len(failed)}",
        f"- Total result rows: {len(rows)}",
        "",
        "## Best So Far",
        "",
        "| experiment | SSIM | PSNR | loss_ma20 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in best:
        lines.append(
            f"| {row['experiment_id']} | {row.get('ssim') or ''} | "
            f"{row.get('psnr') or ''} | {row.get('final_loss_ma20') or ''} |"
        )
    lines.extend(["", "## Failures", ""])
    if failed:
        for row in failed[-20:]:
            lines.append(f"- `{row['experiment_id']}`: {row.get('failure_reason', '')}")
    else:
        lines.append("- None recorded.")
    (EXPERIMENTS / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_manifest(jobs: list[Job]) -> None:
    data = {
        "updated_at": _now(),
        "train_minutes_per_patch_assumption": 30,
        "jobs": [job.__dict__ | {"experiment_id": job.experiment_id} for job in jobs],
    }
    (EXPERIMENTS / "sweep_manifest.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def append_result(row: dict[str, object]) -> None:
    path = EXPERIMENTS / "results.csv"
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in RESULT_FIELDS})


def read_results() -> list[dict[str, str]]:
    path = EXPERIMENTS / "results.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _find_existing_patch(dataset: str, patch_size: int, patch_id: str) -> Path:
    runs = ROOT / "data" / dataset / "runs"
    candidates = sorted(runs.glob(f"*patch{patch_size}*/splat/patches/{patch_id}"))
    for candidate in candidates:
        if (candidate / "patch_metadata.json").exists():
            return candidate
    raise ValueError(f"no existing {dataset} patch{patch_size} {patch_id}; generate patch first")


def _run_logged(command: list[str], *, log_path: Path, env: dict[str, str] | None = None) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n## {_now()}\n$ {' '.join(command)}\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=merged_env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return_code = process.wait()
        log.write(f"[exit_code] {return_code}\n")
    if return_code != 0:
        raise RuntimeError(f"command failed with exit {return_code}: {' '.join(command)}")


def _metric_self_check() -> None:
    left = np_image((32, 32), (128, 128, 128))
    right = np_image((32, 32), (120, 128, 136))
    if not math.isinf(psnr(left, left)):
        raise AssertionError("PSNR identical image should be inf")
    if abs(ssim(left, left) - 1.0) > 1e-6:
        raise AssertionError("SSIM identical image should be 1")
    if ssim(left, right) >= 1.0:
        raise AssertionError("SSIM degraded image should be less than 1")
    expected = -10.0 * math.log10(float(((left - right) ** 2).mean()))
    if abs(psnr(left, right) - expected) > 1e-6:
        raise AssertionError("PSNR known-MSE check failed")
    smoke_dir = EXPERIMENTS / "smoke"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray((left * 255).astype("uint8"), mode="RGB")
    image.save(smoke_dir / "metric_self_check.png")


def _lfs_eval_smoke() -> None:
    """Run a tiny LFS eval job and confirm it exposes eval evidence."""
    config = load_config(DATASETS["dataset1"])
    smoke_dir = EXPERIMENTS / "smoke"
    output_dir = smoke_dir / "lfs_eval"
    if parse_lfs_metrics_csv(output_dir / "metrics.csv"):
        return
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "run.log"
    command = [
        config.tools.lfs_bin,
        "-d",
        str(smoke_dir / "eval_dataset"),
        "-o",
        str(output_dir),
        "--headless",
        "--eval",
        "--test-every",
        str(json.loads((smoke_dir / "holdout_manifest.json").read_text(encoding="utf-8"))["test_every"]),
        "--max-width",
        "512",
        "-i",
        "7000",
        "--max-cap",
        "100000",
        "--strategy",
        config.advanced.splat.train.strategy,
    ]
    _run_logged(command, log_path=log_path)
    text = log_path.read_text(encoding="utf-8", errors="replace").lower()
    if "382 train + 18 val cameras" not in text:
        raise ValueError("LFS smoke did not confirm the expected train/validation split")
    if not parse_lfs_metrics_csv(output_dir / "metrics.csv"):
        raise ValueError("LFS smoke completed but metrics.csv had no PSNR/SSIM rows")


def np_image(shape: tuple[int, int], rgb: tuple[int, int, int]):
    import numpy as np

    array = np.zeros((shape[0], shape[1], 3), dtype=np.float32)
    array[:, :] = [channel / 255.0 for channel in rgb]
    return array


def _result_for(job: Job) -> dict[str, str] | None:
    for row in read_results():
        if row.get("experiment_id") == job.experiment_id and row.get("status") == "complete":
            return row
    return None


def _row(
    job: Job,
    *,
    status: str,
    ssim_value: float | None = None,
    psnr_value: float | None = None,
    final_loss_last: float | None = None,
    final_loss_ma20: float | None = None,
    duration_seconds: float | None = None,
    failure_reason: str = "",
) -> dict[str, object]:
    return {
        "experiment_id": job.experiment_id,
        "group": job.group,
        "dataset": job.dataset,
        "colmap_variant": job.colmap_variant,
        "patch_size": job.patch_size,
        "splat_count": job.splat_count,
        "patch_id": job.patch_id,
        "status": status,
        "ssim": "" if ssim_value is None else round(ssim_value, 6),
        "psnr": "" if psnr_value is None else round(psnr_value, 6),
        "final_loss_last": "" if final_loss_last is None else round(final_loss_last, 6),
        "final_loss_ma20": "" if final_loss_ma20 is None else round(final_loss_ma20, 6),
        "duration_seconds": "" if duration_seconds is None else round(duration_seconds, 3),
        "failure_reason": failure_reason,
        "updated_at": _now(),
    }


def _write_status(name: str, status: str, message: str) -> None:
    (EXPERIMENTS / f"{name}_status.json").write_text(
        json.dumps({"status": status, "message": message, "updated_at": _now()}, indent=2) + "\n",
        encoding="utf-8",
    )


def _apply_config_overrides(data: dict[str, object], overrides: dict[str, object]) -> None:
    for dotted, value in overrides.items():
        target = data
        parts = dotted.split(".")
        for part in parts[:-1]:
            target = target[part]  # type: ignore[index,assignment]
        target[parts[-1]] = value  # type: ignore[index]


def _float_or_neg_inf(value: object) -> float:
    try:
        if value in {None, ""}:
            return -math.inf
        return float(value)
    except (TypeError, ValueError):
        return -math.inf


def _float_or_inf(value: object) -> float:
    try:
        if value in {None, ""}:
            return math.inf
        return float(value)
    except (TypeError, ValueError):
        return math.inf


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
