"""Python-owned image metrics for saved LFS comparison renders."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
from skimage.metrics import peak_signal_noise_ratio, structural_similarity

from reefs.eval.lpips import compute_lfs_eval_lpips, load_lfs_comparison_images


def write_python_eval_metrics(
    *,
    output_dir: Path,
    metrics_path: Path,
    iterations: list[int],
    compute_lpips: bool,
    num_gaussians: int | None,
    expected_manifest: Path | None = None,
) -> tuple[dict[str, float | int | str], list[dict[str, float | int | str]]]:
    """Compute PSNR/SSIM/LPIPS from saved comparison images and write metrics.csv."""
    _delete_lfs_metric_artifacts(output_dir)
    expected_sizes, target_image_source = _manifest_fields(expected_manifest)
    metric_source = f"python_{target_image_source or 'image_metrics'}"
    lpips_values = (
        compute_lfs_eval_lpips(output_dir=output_dir, iterations=iterations)
        if compute_lpips
        else {}
    )
    rows: list[dict[str, float | int | str]] = []
    for iteration in iterations:
        paths = sorted((output_dir / f"eval_step_{iteration}").glob("*.png"))
        if not paths:
            raise ValueError(f"missing saved LFS comparison images for eval step {iteration}: {output_dir}")
        psnr_values: list[float] = []
        ssim_values: list[float] = []
        for path in paths:
            gt, rendered = load_lfs_comparison_images(path)
            _validate_size(path=path, size=gt.size, expected_sizes=expected_sizes)
            if gt.size != rendered.size:
                raise ValueError(f"LFS comparison halves have different sizes: {path}")
            gt_array = np.asarray(gt, dtype=np.float32)
            rendered_array = np.asarray(rendered, dtype=np.float32)
            psnr_values.append(float(peak_signal_noise_ratio(gt_array, rendered_array, data_range=255.0)))
            ssim_values.append(
                float(
                    structural_similarity(
                        gt_array,
                        rendered_array,
                        channel_axis=2,
                        data_range=255.0,
                        win_size=_ssim_window(gt.size),
                    )
                )
            )
        row: dict[str, float | int | str] = {
            "iteration": iteration,
            "psnr": _mean(psnr_values),
            "ssim": _mean(ssim_values),
            "time_per_image": 0.0,
            "num_gaussians": num_gaussians or 0,
            "metric_source": metric_source,
        }
        if compute_lpips:
            if iteration not in lpips_values:
                raise ValueError(f"missing LPIPS value for eval step {iteration}: {output_dir}")
            row["lpips"] = lpips_values[iteration]
        rows.append(row)
    _write_metrics_csv(metrics_path, rows, include_lpips=compute_lpips)
    _write_metric_metadata(
        output_dir=output_dir,
        rows=rows,
        compute_lpips=compute_lpips,
        expected_sizes=expected_sizes,
        metric_source=metric_source,
    )
    return rows[-1], rows


def _delete_lfs_metric_artifacts(output_dir: Path) -> None:
    for name in ("metrics.csv", "metrics_report.txt"):
        path = output_dir / name
        if path.exists():
            path.unlink()


def _manifest_fields(manifest_path: Path | None) -> tuple[set[tuple[int, int]], str]:
    if manifest_path is None or not manifest_path.exists():
        return set(), ""
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    dimensions = data.get("holdout_image_dimensions")
    if not isinstance(dimensions, dict):
        return set(), str(data.get("target_image_source") or "")
    sizes: set[tuple[int, int]] = set()
    for value in dimensions.values():
        if not isinstance(value, dict) or "width" not in value or "height" not in value:
            continue
        sizes.add((int(value["width"]), int(value["height"])))
    return sizes, str(data.get("target_image_source") or "")


def _validate_size(*, path: Path, size: tuple[int, int], expected_sizes: set[tuple[int, int]]) -> None:
    if expected_sizes and size not in expected_sizes:
        raise ValueError(
            f"LFS comparison image is not at expected eval target size: {path} has {size}, "
            f"expected one of {sorted(expected_sizes)}"
        )


def _mean(values: list[float]) -> float:
    if not values:
        raise ValueError("cannot average an empty metric list")
    if any(math.isinf(value) for value in values):
        return math.inf
    return float(sum(values) / len(values))


def _ssim_window(size: tuple[int, int]) -> int:
    shortest = min(size)
    if shortest < 3:
        raise ValueError(f"SSIM requires eval images at least 3 px on each side, got {size}")
    return min(7, shortest if shortest % 2 == 1 else shortest - 1)


def _write_metrics_csv(
    path: Path,
    rows: list[dict[str, float | int | str]],
    *,
    include_lpips: bool,
) -> None:
    fields = ["iteration", "psnr", "ssim"]
    if include_lpips:
        fields.append("lpips")
    fields.extend(["time_per_image", "num_gaussians", "metric_source"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _format_value(row.get(field, "")) for field in fields})


def _format_value(value: object) -> object:
    if isinstance(value, float):
        if math.isinf(value):
            return "inf"
        return f"{value:.6f}"
    return value


def _write_metric_metadata(
    *,
    output_dir: Path,
    rows: list[dict[str, float | int | str]],
    compute_lpips: bool,
    expected_sizes: set[tuple[int, int]],
    metric_source: str,
) -> None:
    payload = {
        "metric_source": metric_source,
        "psnr": "skimage.metrics.peak_signal_noise_ratio(data_range=255)",
        "ssim": "skimage.metrics.structural_similarity(channel_axis=2, data_range=255)",
        "lpips": "lpips.LPIPS(net='alex')" if compute_lpips else None,
        "expected_eval_sizes": [{"width": width, "height": height} for width, height in sorted(expected_sizes)],
        "iterations": [int(row["iteration"]) for row in rows],
    }
    (output_dir / "python_metrics.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
