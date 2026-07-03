"""Markdown reports for ablation sweeps."""

from __future__ import annotations

from pathlib import Path

from reefs.experiments.ablations.config import AblationConfig
from reefs.experiments.ablations.grid import build_sfm_jobs, build_splat_jobs
from reefs.experiments.ablations.ledger import read_rows
from reefs.experiments.ablations.metrics import rank_splat_rows


def write_plan_markdown(config: AblationConfig, path: Path) -> None:
    """Write the plain-English ablation plan."""
    lines = [
        "# 3DReefs Ablation Plan",
        "",
        "This experiment compares SfM settings first, then reuses the best overall SfM result for splat sweeps.",
        "",
        "## Datasets",
        "",
        "| dataset | config | project |",
        "| --- | --- | --- |",
    ]
    for dataset in config.datasets:
        lines.append(f"| {dataset.name} | `{dataset.config}` | `{dataset.project_dir}` |")
    lines.extend(
        [
            "",
            "## SfM Sweep",
            "",
            "Each SfM job runs one dataset plus one Stage 1 variant, generates patch400 patches, and records reconstruction metrics. Eval splats are limited to the selected validation patches.",
            "",
            "| done | dataset | variant | patch size | validation splat cap | description |",
            "| --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for job in build_sfm_jobs(config):
        lines.append(
            f"| [ ] | {job.dataset.name} | {job.variant.name} | {job.patch_size} | "
            f"{job.splat_count} | {job.variant.description} |"
        )
    lines.extend(
        [
            "",
            "## Splat Sweep",
            "",
            "The later splat sweep reuses the best overall SfM result. Patch selection for that sweep is controlled separately from the all-patch SfM eval.",
            "",
            "| done | dataset | patch size | splat cap | max width |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for job in build_splat_jobs(config):
        lines.append(f"| [ ] | {job.dataset.name} | {job.patch_size} | {job.splat_count} | {job.max_width} |")
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            "- SfM: registered images %, components, reprojection error, sparse point count, track length, verified pairs, cross-camera pairs.",
            "- Splat: held-out SSIM/PSNR/LPIPS when available, training time, peak RAM/VRAM, PLY size, and final actual splat count.",
            "- Holdouts: canonical 10% held-out images are scoped per SfM run because patch contents differ across variants.",
            "- Cleanup, merge, and SOG are not part of the formal sweeps by default; keep them available for selected visual follow-up runs.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_progress_markdown(output_root: Path) -> None:
    """Write the current progress report."""
    sfm_rows = read_rows(output_root / "results_sfm.csv")
    splat_rows = read_rows(output_root / "results_splat.csv")
    final_rows = read_rows(output_root / "results_final.csv")
    lines = [
        "# Ablation Progress",
        "",
        "## SfM Jobs",
        "",
        "| done | job | dataset | variant | status | runtime h | registered % | keypoints/image | components | cross-camera pairs | selected patches | failure |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in sfm_rows:
        done = "[x]" if str(row.get("status", "")).startswith("complete") else "[ ]"
        runtime_h = _hours(row.get("sfm_runtime_seconds"))
        lines.append(
            f"| {done} | `{row.get('job_id', '')}` | {row.get('dataset', '')} | {row.get('variant', '')} | "
            f"{row.get('status', '')} | {runtime_h} | {_short(row.get('registered_images_percent'))} | "
            f"{_short(row.get('mean_keypoints_per_image'))} | {row.get('connected_components', '')} | "
            f"{row.get('cross_camera_verified_pairs', '')} | "
            f"{row.get('selected_patches', '')} | {row.get('failure_reason', '')} |"
        )
    lines.extend(
        [
            "",
            "## Splat Jobs",
            "",
            "| done | job | dataset | patch | status | eval target | eval size | SSIM | PSNR | LPIPS | runtime h | PLY bytes | splats | failure |",
            "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in splat_rows:
        done = "[x]" if str(row.get("status", "")).startswith("complete") else "[ ]"
        eval_size = _image_size(row.get("eval_image_width"), row.get("eval_image_height"))
        lines.append(
            f"| {done} | `{row.get('job_id', '')}` | {row.get('dataset', '')} | {row.get('patch_id', '')} | "
            f"{row.get('status', '')} | {row.get('eval_target_source', '')} | {eval_size} | "
            f"{_short(row.get('ssim'))} | {_short(row.get('psnr'))} | "
            f"{_short(row.get('lpips'))} | {_hours(row.get('training_runtime_seconds'))} | "
            f"{row.get('output_ply_size_bytes', '')} | "
            f"{row.get('actual_splat_count', '')} | {row.get('failure_reason', '')} |"
        )
    ranked_splats = [
        row for row in rank_splat_rows(splat_rows) if str(row.get("status", "")).startswith("complete")
    ][:10]
    lines.extend(
        [
            "",
            "## Best Splat Rows",
            "",
            "Rows are ranked by completed status, higher SSIM, higher PSNR, then lower LPIPS when present.",
            "",
            "| rank | job | dataset | patch | eval target | SSIM | PSNR | LPIPS | runtime h |",
            "| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for index, row in enumerate(ranked_splats, start=1):
        lines.append(
            f"| {index} | `{row.get('job_id', '')}` | {row.get('dataset', '')} | {row.get('patch_id', '')} | "
            f"{row.get('eval_target_source', '')} | {_short(row.get('ssim'))} | {_short(row.get('psnr'))} | "
            f"{_short(row.get('lpips'))} | {_hours(row.get('training_runtime_seconds'))} |"
        )
    lines.extend(
        [
            "",
            "## Final Runs",
            "",
            "| done | job | dataset | status | runtime h | PLY bytes | SOG bytes | splats | failure |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in final_rows:
        done = "[x]" if str(row.get("status", "")).startswith("complete") else "[ ]"
        lines.append(
            f"| {done} | `{row.get('job_id', '')}` | {row.get('dataset', '')} | {row.get('status', '')} | "
            f"{_hours(row.get('runtime_seconds'))} | {row.get('merged_ply_size_bytes', '')} | "
            f"{row.get('sog_size_bytes', '')} | {row.get('actual_splat_count', '')} | {row.get('failure_reason', '')} |"
        )
    (output_root / "progress.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _hours(value: object) -> str:
    try:
        return f"{float(value) / 3600.0:.2f}" if str(value) else ""
    except ValueError:
        return ""


def _short(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{number:.4f}"


def _image_size(width: object, height: object) -> str:
    if not str(width or "") or not str(height or ""):
        return ""
    return f"{width}x{height}"
