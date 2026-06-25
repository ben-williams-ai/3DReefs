"""Command implementation for ablation sweeps."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from reefs.config.loader import load_config
from reefs.experiments.ablations.config import AblationConfig, load_ablation_config
from reefs.experiments.ablations.grid import SfMJob, build_sfm_jobs, build_splat_jobs, select_even_patch_ids
from reefs.experiments.ablations.ledger import (
    FINAL_FIELDS,
    MANIFEST_FIELDS,
    SFM_FIELDS,
    SPLAT_FIELDS,
    atomic_write_csv,
    completed_job_ids,
    upsert_row,
)
from reefs.experiments.ablations.metrics import sfm_metrics
from reefs.experiments.ablations.report import write_plan_markdown, write_progress_markdown
from reefs.experiments.ablations.resource import ResourceSampler
from reefs.experiments.ablations.time_utils import utc_now
from reefs.io.paths import derive_project_paths
from reefs.io.yaml_json import write_json


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONFIG = REPO_ROOT / "experiments" / "ablations" / "ablation_config.yml"
MAIN_PY = REPO_ROOT / "main.py"


def main(argv: list[str] | None = None) -> int:
    """Run the ablation CLI."""
    parser = argparse.ArgumentParser(description="Run 3DReefs ablation sweeps.")
    parser.add_argument("command", choices=["manifest", "smoke", "prepare", "run", "report"])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--phase", choices=["sfm", "splat", "final", "all"], default="all")
    parser.add_argument("--simulate", action="store_true", help="Write simulated outputs instead of running tools.")
    parser.add_argument("--force-job", action="append", default=[], help="Re-run a completed job id.")
    args = parser.parse_args(argv)
    config = load_ablation_config(args.config, repo_root=REPO_ROOT)
    if args.command == "manifest":
        initialise_outputs(config)
        return 0
    if args.command == "smoke":
        smoke(config=config, simulate=args.simulate)
        return 0
    if args.command == "prepare":
        prepare(config)
        return 0
    if args.command == "report":
        write_progress_markdown(config.output_root)
        return 0
    if args.phase in {"sfm", "all"}:
        run_sfm_phase(config=config, force_jobs=set(args.force_job))
    if args.phase in {"splat", "final", "all"}:
        raise SystemExit("Only the SfM phase is implemented for the initial ablation run.")
    return 0


def initialise_outputs(config: AblationConfig) -> None:
    """Create planned ledgers and the review plan."""
    config.output_root.mkdir(parents=True, exist_ok=True)
    write_plan_markdown(config, config.output_root / "plan.md")
    manifest_rows: list[dict[str, object]] = []
    for job in build_sfm_jobs(config):
        manifest_rows.append(
            {
                "job_id": job.job_id,
                "phase": "sfm",
                "dataset": job.dataset.name,
                "variant": job.variant.name,
                "patch_size": job.patch_size,
                "splat_count": job.splat_count,
                "max_width": "",
                "status": "planned",
            }
        )
    for job in build_splat_jobs(config):
        manifest_rows.append(
            {
                "job_id": job.job_id,
                "phase": "splat",
                "dataset": job.dataset.name,
                "variant": job.sfm_variant,
                "patch_size": job.patch_size,
                "splat_count": job.splat_count,
                "max_width": job.max_width,
                "status": "planned",
            }
        )
    atomic_write_csv(config.output_root / "manifest.csv", MANIFEST_FIELDS, manifest_rows)
    for filename, fields in [
        ("results_sfm.csv", SFM_FIELDS),
        ("results_splat.csv", SPLAT_FIELDS),
        ("results_final.csv", FINAL_FIELDS),
    ]:
        path = config.output_root / filename
        if not path.exists():
            atomic_write_csv(path, fields, [])
    write_progress_markdown(config.output_root)


def smoke(*, config: AblationConfig, simulate: bool) -> None:
    """Run or simulate smoke checks."""
    initialise_outputs(config)
    if not simulate:
        raise SystemExit("Only simulated smoke is implemented; pass --simulate.")
    preview = config.output_root / "smoke_preview"
    if preview.exists():
        shutil.rmtree(preview)
    preview.mkdir(parents=True)
    fake_config = AblationConfig(
        output_root=preview,
        datasets=config.datasets,
        sfm_variants=config.sfm_variants,
        patch_sizes=config.patch_sizes,
        splat_counts=config.splat_counts,
        max_widths=config.max_widths,
        validation_patch_count=config.validation_patch_count,
        holdout_fraction=config.holdout_fraction,
        sfm_timeout_hours=config.sfm_timeout_hours,
        default_patch_size=config.default_patch_size,
        default_splat_count=config.default_splat_count,
        lfs_eval_every_iterations=config.lfs_eval_every_iterations,
        run_validation_splats_for_sfm=config.run_validation_splats_for_sfm,
    )
    initialise_outputs(fake_config)
    sfm_rows = []
    for index, job in enumerate(build_sfm_jobs(config)):
        sfm_rows.append(
            {
                "job_id": job.job_id,
                "dataset": job.dataset.name,
                "variant": job.variant.name,
                "status": "complete" if index % 3 else "failed",
                "sfm_runtime_seconds": 12_000 + index * 300,
                "patch_runtime_seconds": 120,
                "registered_images": 8000 + index,
                "total_images": 8100,
                "registered_images_percent": 98.8,
                "sparse_model_count": 1,
                "connected_components": 1,
                "largest_component_images": 8000,
                "largest_component_percent": 100.0,
                "mean_reprojection_error_px": 0.45,
                "median_reprojection_error_px": 0.31,
                "sparse_point_count": 3_000_000,
                "mean_track_length": 4.8,
                "median_track_length": 4,
                "verified_image_pairs": 65_000,
                "cross_camera_verified_pairs": 12_000,
                "selected_patches": "p000;p004;p009;p013;p017",
                "peak_ram_mib": 64_000,
                "peak_vram_mib": 28_000,
                "failure_reason": "" if index % 3 else "simulated failure row",
                "updated_at": utc_now(),
            }
        )
    atomic_write_csv(preview / "results_sfm.csv", SFM_FIELDS, sfm_rows)
    splat_rows = [
        {
            "job_id": "splat_dataset1_best_patch400_2m_w4096",
            "dataset": "dataset1",
            "variant": "best",
            "patch_id": "p000",
            "patch_size": 400,
            "splat_count": 2_000_000,
            "max_width": 4096,
            "status": "complete",
            "ssim": 0.71,
            "psnr": 23.4,
            "training_runtime_seconds": 2200,
            "output_ply_size_bytes": 850_000_000,
            "output_sog_size_bytes": 150_000_000,
            "actual_splat_count": 1_980_000,
            "peak_ram_mib": 48_000,
            "peak_vram_mib": 32_000,
            "failure_reason": "",
            "updated_at": utc_now(),
        }
    ]
    atomic_write_csv(preview / "results_splat.csv", SPLAT_FIELDS, splat_rows)
    atomic_write_csv(preview / "results_final.csv", FINAL_FIELDS, [])
    holdout = preview / "holdouts" / "dataset1" / "patch400" / "p000.json"
    write_json(
        holdout,
        {
            "patch_id": "p000",
            "holdout_images": ["cam1/example_001.jpg", "cam2/example_010.jpg"],
            "train_images": ["cam1/example_002.jpg"],
            "test_every": 2,
        },
    )
    write_json(preview / "resource_summary.json", {"peak_ram_mib": 64_000, "peak_vram_mib": 32_000, "samples": 3})
    write_progress_markdown(preview)


def prepare(config: AblationConfig) -> None:
    """Archive old run directories and create clean run roots."""
    initialise_outputs(config)
    archive_root = config.output_root / "archived_runs" / utc_now().replace(":", "")
    archive_manifest: list[dict[str, object]] = []
    for dataset in config.datasets:
        runs = dataset.project_dir / "runs"
        if runs.exists() and any(runs.iterdir()):
            target = archive_root / dataset.name / "runs"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(runs), str(target))
            archive_manifest.append({"dataset": dataset.name, "source": str(runs), "archive": str(target)})
        runs.mkdir(parents=True, exist_ok=True)
    write_json(archive_root / "archive_manifest.json", archive_manifest)


def run_sfm_phase(*, config: AblationConfig, force_jobs: set[str]) -> None:
    """Run all configured SfM jobs."""
    initialise_outputs(config)
    completed = completed_job_ids(config.output_root / "results_sfm.csv") - force_jobs
    for job in build_sfm_jobs(config):
        if job.job_id in completed:
            continue
        row = _run_one_sfm_job(config=config, job=job)
        upsert_row(config.output_root / "results_sfm.csv", SFM_FIELDS, row)
        write_progress_markdown(config.output_root)


def _run_one_sfm_job(*, config: AblationConfig, job: SfMJob) -> dict[str, object]:
    job_dir = config.output_root / "jobs" / job.job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    run_dir = job.dataset.project_dir / "runs" / job.job_id
    started = perf_counter()
    resource_summary = None
    resource_sampler = ResourceSampler(job_dir / "resource_samples.csv", interval_seconds=30)
    try:
        with resource_sampler:
            if _sfm_outputs_exist(run_dir):
                sfm_seconds = _existing_command_duration(job_dir / "sfm_command.log", run_dir=run_dir)
            else:
                sfm_seconds = _run_pipeline_command(
                    job=job,
                    steps="sfm",
                    overrides=job.variant.overrides,
                    timeout_seconds=config.sfm_timeout_hours * 3600,
                    log_path=job_dir / "sfm_command.log",
                )
        resource_summary = resource_sampler.summary()
        patch_seconds: float | str = ""
        patch_ids: list[str] = []
        if config.run_validation_splats_for_sfm:
            patch_seconds = _run_pipeline_command(
                job=job,
                steps="splat.patch",
                overrides={
                    **job.variant.overrides,
                    "advanced.splat.patching.max_cameras": job.patch_size,
                },
                timeout_seconds=None,
                log_path=job_dir / "patch_command.log",
            )
            patches_dir = run_dir / "splat" / "patches"
            patch_ids = select_even_patch_ids(
                [path.name for path in patches_dir.iterdir() if path.is_dir()] if patches_dir.exists() else [],
                config.validation_patch_count,
            )
        pipeline_config = load_config(job.dataset.config)
        derived = derive_project_paths(pipeline_config, None)
        metrics = sfm_metrics(
            colmap_bin=pipeline_config.tools.colmap_bin,
            run_dir=run_dir,
            project_images_dir=derived.raw_images,
        )
        quality_warning = _combine_warnings(
            _sfm_quality_warning(metrics),
            _sfm_log_warning(
                job_dir / "sfm_command.log",
                run_dir / "logs" / "colmap.log",
            ),
        )
        write_json(job_dir / "sfm_metrics.json", metrics)
        return {
            "job_id": job.job_id,
            "dataset": job.dataset.name,
            "variant": job.variant.name,
            "status": "complete_with_warnings" if quality_warning else "complete",
            "sfm_runtime_seconds": round(sfm_seconds, 3),
            "patch_runtime_seconds": round(patch_seconds, 3) if isinstance(patch_seconds, float) else patch_seconds,
            **metrics,
            "selected_patches": ";".join(patch_ids),
            "peak_ram_mib": resource_summary.peak_ram_mib if resource_summary else "",
            "peak_vram_mib": resource_summary.peak_vram_mib if resource_summary else "",
            "failure_reason": quality_warning,
            "updated_at": utc_now(),
        }
    except subprocess.TimeoutExpired:
        resource_summary = resource_summary or resource_sampler.summary()
        return _sfm_failure_row(job, started, "sfm_timeout_exceeded_20h", resource_summary)
    except Exception as exc:
        resource_summary = resource_summary or resource_sampler.summary()
        return _sfm_failure_row(job, started, str(exc), resource_summary)


def _run_pipeline_command(
    *,
    job: SfMJob,
    steps: str,
    overrides: dict[str, object],
    timeout_seconds: float | None,
    log_path: Path,
) -> float:
    (job.dataset.project_dir / "runs" / job.job_id).mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(MAIN_PY),
        "--config",
        str(job.dataset.config),
        "--steps",
        steps,
        "--resume-policy",
        "overwrite",
        "--run-id",
        job.job_id,
    ]
    for key, value in overrides.items():
        command.extend([f"--{key}", _override_value(value)])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = perf_counter()
    with log_path.open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(command) + "\n\n")
        log.flush()
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    duration = perf_counter() - start
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n[exit_code] {completed.returncode}\n")
        log.write(f"[duration_seconds] {duration:.6f}\n")
    if completed.returncode != 0:
        raise RuntimeError(f"pipeline command failed with exit {completed.returncode}: {log_path}")
    return duration


def _sfm_outputs_exist(run_dir: Path) -> bool:
    """Return whether the run has enough SfM outputs for metric extraction."""
    sparse_bin = run_dir / "sfm" / "selected_sparse"
    return all(
        path.exists()
        for path in [
            sparse_bin / "cameras.bin",
            sparse_bin / "images.bin",
            sparse_bin / "points3D.bin",
            run_dir / "sfm" / "database.db",
        ]
    )


def _existing_command_duration(log_path: Path, *, run_dir: Path) -> float:
    """Read a completed command duration from a prior ablation command log."""
    if not log_path.exists():
        return _pipeline_timing_duration(run_dir / "timings.json")
    marker = "[duration_seconds]"
    duration: float | None = None
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith(marker):
                try:
                    duration = float(line.split("]", 1)[1].strip())
                except (IndexError, ValueError):
                    continue
    return duration or _pipeline_timing_duration(run_dir / "timings.json")


def _sfm_quality_warning(metrics: dict[str, object]) -> str:
    """Return a warning string when COLMAP exited cleanly but the SfM graph looks unusable."""
    warnings: list[str] = []
    largest_component = _float_metric(metrics.get("largest_component_percent"))
    cross_camera_pairs = _float_metric(metrics.get("cross_camera_verified_pairs"))
    mean_error = _float_metric(metrics.get("mean_reprojection_error_px"))
    registered_percent = _float_metric(metrics.get("registered_images_percent"))
    if largest_component is not None and largest_component < 80.0:
        warnings.append(f"largest_component_below_80_percent:{largest_component:.2f}")
    if registered_percent is not None and registered_percent >= 95.0 and cross_camera_pairs == 0:
        warnings.append("zero_cross_camera_pairs_with_high_registration")
    if mean_error == 0.0:
        warnings.append("zero_mean_reprojection_error")
    return ";".join(warnings)


def _sfm_log_warning(*log_paths: Path) -> str:
    """Return warnings for COLMAP failures that can still exit with code 0."""
    chunks: list[str] = []
    for log_path in log_paths:
        if not log_path.exists():
            continue
        try:
            chunks.append(log_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    text = "\n".join(chunks)
    warnings: list[str] = []
    if "CUDSS_STATUS_ALLOC_FAILED" in text:
        warnings.append("colmap_cudss_alloc_failed")
    if "Termination: FAILURE" in text:
        warnings.append("colmap_ceres_termination_failure")
    return ";".join(warnings)


def _combine_warnings(*warning_groups: str) -> str:
    """Combine semicolon-separated warning groups without duplicates."""
    warnings: list[str] = []
    for group in warning_groups:
        for warning in group.split(";"):
            warning = warning.strip()
            if warning and warning not in warnings:
                warnings.append(warning)
    return ";".join(warnings)


def _float_metric(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pipeline_timing_duration(path: Path) -> float:
    """Return total recorded pipeline stage duration when outer logging was interrupted."""
    if not path.exists():
        return 0.0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0.0
    stages = data.get("stages")
    if not isinstance(stages, list):
        return 0.0
    total = 0.0
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        try:
            total += float(stage.get("duration_seconds") or 0.0)
        except (TypeError, ValueError):
            continue
    return total


def _override_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def _sfm_failure_row(job: SfMJob, started: float, reason: str, resource_summary) -> dict[str, object]:
    return {
        "job_id": job.job_id,
        "dataset": job.dataset.name,
        "variant": job.variant.name,
        "status": "failed",
        "sfm_runtime_seconds": round(perf_counter() - started, 3),
        "patch_runtime_seconds": "",
        "registered_images": "",
        "total_images": "",
        "registered_images_percent": "",
        "sparse_model_count": "",
        "connected_components": "",
        "largest_component_images": "",
        "largest_component_percent": "",
        "mean_reprojection_error_px": "",
        "median_reprojection_error_px": "",
        "sparse_point_count": "",
        "mean_track_length": "",
        "median_track_length": "",
        "verified_image_pairs": "",
        "cross_camera_verified_pairs": "",
        "selected_patches": "",
        "peak_ram_mib": resource_summary.peak_ram_mib if resource_summary else "",
        "peak_vram_mib": resource_summary.peak_vram_mib if resource_summary else "",
        "failure_reason": reason,
        "updated_at": utc_now(),
    }
