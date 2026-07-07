"""LPIPS helpers for LFS evaluation comparison images."""

from __future__ import annotations

import csv
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image


EVAL_IMAGE_SEPARATOR_PX = 4


def compute_lfs_eval_lpips(
    *,
    output_dir: Path,
    iterations: Iterable[int],
    model_factory: Callable[[torch.device], Any] | None = None,
) -> dict[int, float]:
    """Return mean LPIPS for each LFS eval step with saved comparison images."""
    image_sets = {
        iteration: sorted((output_dir / f"eval_step_{iteration}").glob("*.png"))
        for iteration in sorted(set(int(value) for value in iterations))
    }
    image_sets = {iteration: paths for iteration, paths in image_sets.items() if paths}
    if not image_sets:
        return {}
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = (model_factory or _default_lpips_model)(device)
    if hasattr(model, "eval"):
        model.eval()
    results: dict[int, float] = {}
    with torch.no_grad():
        for iteration, paths in image_sets.items():
            values: list[float] = []
            for path in paths:
                gt, rendered = _load_lfs_comparison(path, device)
                value = model(gt, rendered)
                values.append(float(value.reshape(-1)[0].detach().cpu()))
            if values:
                results[iteration] = float(sum(values) / len(values))
    return results


def _default_lpips_model(device: torch.device):
    import lpips

    return lpips.LPIPS(net="alex").to(device)


def _load_lfs_comparison(path: Path, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    """Split an LFS GT/render comparison PNG into LPIPS-normalised tensors."""
    gt, rendered = load_lfs_comparison_images(path)
    return _image_to_lpips_tensor(gt, device), _image_to_lpips_tensor(rendered, device)


def load_lfs_comparison_images(path: Path) -> tuple[Image.Image, Image.Image]:
    """Split an LFS GT/render comparison PNG into RGB PIL images."""
    image = Image.open(path).convert("RGB")
    width, height = image.size
    single_width = (width - EVAL_IMAGE_SEPARATOR_PX) // 2
    if single_width <= 0 or width != single_width * 2 + EVAL_IMAGE_SEPARATOR_PX:
        raise ValueError(f"unexpected LFS eval image shape for LPIPS: {path} ({width}x{height})")
    gt = image.crop((0, 0, single_width, height))
    rendered = image.crop((single_width + EVAL_IMAGE_SEPARATOR_PX, 0, width, height))
    return gt, rendered


def _image_to_lpips_tensor(image: Image.Image, device: torch.device) -> torch.Tensor:
    array = np.asarray(image, dtype=np.float32) / 127.5 - 1.0
    tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0)
    return tensor.to(device)


def add_lpips_to_lfs_metrics(
    *,
    output_dir: Path,
    metrics_path: Path,
    iterations: Iterable[int],
    model_factory: Callable[[torch.device], Any] | None = None,
) -> dict[int, float]:
    """Compute LPIPS from saved LFS eval images and merge values into metrics.csv.

    Kept for legacy tests and older callers. New eval metrics are written by
    ``reefs.eval.image_metrics`` without trusting LFS metric rows.
    """
    lpips_by_iteration = compute_lfs_eval_lpips(
        output_dir=output_dir,
        iterations=iterations,
        model_factory=model_factory,
    )
    if lpips_by_iteration:
        _merge_lpips_column(metrics_path, lpips_by_iteration)
    return lpips_by_iteration


def _merge_lpips_column(metrics_path: Path, lpips_by_iteration: dict[int, float]) -> None:
    if not metrics_path.exists():
        return
    with metrics_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return
        fieldnames = list(reader.fieldnames)
        rows = list(reader)
    if "lpips" not in fieldnames:
        insert_at = fieldnames.index("time_per_image") if "time_per_image" in fieldnames else len(fieldnames)
        fieldnames.insert(insert_at, "lpips")
    for row in rows:
        try:
            iteration = int(float(row.get("iteration") or row.get("Iteration") or "nan"))
        except ValueError:
            continue
        if iteration in lpips_by_iteration:
            row["lpips"] = f"{lpips_by_iteration[iteration]:.6f}"
    tmp = metrics_path.with_suffix(metrics_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(metrics_path)
