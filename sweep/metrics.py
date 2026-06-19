"""Small metric helpers for sweep evaluation."""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class LossSummary:
    """Smoothed final loss values parsed from LFS loss history."""

    final_loss_last: float | None
    final_loss_ma20: float | None
    loss_count: int


def image_rgb(path: Path) -> np.ndarray:
    """Read an image as RGB float32 values in [0, 1]."""
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        return np.asarray(rgb, dtype=np.float32) / 255.0


def psnr(reference: np.ndarray, rendered: np.ndarray) -> float:
    """Return PSNR for same-shaped RGB images in [0, 1]."""
    _validate_pair(reference, rendered)
    mse = float(np.mean((reference - rendered) ** 2))
    if mse == 0.0:
        return math.inf
    return -10.0 * math.log10(mse)


def ssim(reference: np.ndarray, rendered: np.ndarray) -> float:
    """Return RGB mean SSIM with an 11x11 Gaussian window."""
    _validate_pair(reference, rendered)
    kernel = _gaussian_kernel(size=11, sigma=1.5)
    scores = [
        _ssim_single_channel(reference[:, :, channel], rendered[:, :, channel], kernel)
        for channel in range(3)
    ]
    return float(np.mean(scores))


def pair_metrics(reference_path: Path, rendered_path: Path) -> dict[str, float]:
    """Return SSIM and PSNR for one rendered/ground-truth image pair."""
    reference = image_rgb(reference_path)
    rendered = image_rgb(rendered_path)
    return {"ssim": ssim(reference, rendered), "psnr": psnr(reference, rendered)}


def summarise_loss_history(path: Path, *, tail_count: int = 20) -> LossSummary:
    """Return last loss and moving average over the final rows."""
    if not path.exists():
        return LossSummary(None, None, 0)
    values: list[float] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            value = row.get("loss")
            if value not in {None, ""}:
                values.append(float(value))
    if not values:
        return LossSummary(None, None, 0)
    tail = values[-tail_count:]
    return LossSummary(values[-1], sum(tail) / len(tail), len(values))


def parse_lfs_log_metrics(log_path: Path) -> dict[str, float]:
    """Parse cheap native eval metrics from LFS logs when they are present."""
    if not log_path.exists():
        return {}
    text = log_path.read_text(encoding="utf-8", errors="replace")
    found: dict[str, float] = {}
    for name, pattern in {
        "ssim": r"\bSSIM\b[^0-9+-]*([-+]?\d+(?:\.\d+)?)",
        "psnr": r"\bPSNR\b[^0-9+-]*([-+]?\d+(?:\.\d+)?)",
    }.items():
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            found[name] = float(matches[-1])
    return found


def parse_lfs_metrics_csv(path: Path) -> dict[str, float]:
    """Read the last PSNR/SSIM row from LFS native metrics.csv."""
    if not path.exists():
        return {}
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("psnr") and row.get("ssim"):
                rows.append(row)
    if not rows:
        return {}
    last = rows[-1]
    return {"psnr": float(last["psnr"]), "ssim": float(last["ssim"])}


def summarise_lfs_log_loss(log_path: Path, *, tail_count: int = 20) -> LossSummary:
    """Return loss summary parsed from LFS progress lines."""
    if not log_path.exists():
        return LossSummary(None, None, 0)
    values = [
        float(match.group(1))
        for match in re.finditer(
            r"\bLoss:\s*([0-9.eE+-]+)",
            log_path.read_text(encoding="utf-8", errors="replace"),
        )
    ]
    if not values:
        return LossSummary(None, None, 0)
    tail = values[-tail_count:]
    return LossSummary(values[-1], sum(tail) / len(tail), len(values))


def _validate_pair(reference: np.ndarray, rendered: np.ndarray) -> None:
    if reference.shape != rendered.shape:
        raise ValueError(f"image shapes differ: {reference.shape} vs {rendered.shape}")
    if reference.ndim != 3 or reference.shape[2] != 3:
        raise ValueError(f"expected RGB images, got shape {reference.shape}")
    if not np.isfinite(reference).all() or not np.isfinite(rendered).all():
        raise ValueError("image contains NaN or infinite values")


def _gaussian_kernel(*, size: int, sigma: float) -> np.ndarray:
    radius = size // 2
    axis = np.arange(-radius, radius + 1, dtype=np.float32)
    kernel = np.exp(-(axis**2) / (2.0 * sigma**2))
    kernel /= np.sum(kernel)
    return kernel


def _blur(channel: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    radius = len(kernel) // 2
    padded = np.pad(channel, ((0, 0), (radius, radius)), mode="reflect")
    horizontal = np.empty_like(channel, dtype=np.float32)
    for column in range(channel.shape[1]):
        horizontal[:, column] = np.sum(padded[:, column : column + len(kernel)] * kernel, axis=1)
    padded = np.pad(horizontal, ((radius, radius), (0, 0)), mode="reflect")
    vertical = np.empty_like(channel, dtype=np.float32)
    for row in range(channel.shape[0]):
        vertical[row, :] = np.sum(padded[row : row + len(kernel), :] * kernel[:, None], axis=0)
    return vertical


def _ssim_single_channel(left: np.ndarray, right: np.ndarray, kernel: np.ndarray) -> float:
    c1 = 0.01**2
    c2 = 0.03**2
    mu_left = _blur(left, kernel)
    mu_right = _blur(right, kernel)
    mu_left_sq = mu_left * mu_left
    mu_right_sq = mu_right * mu_right
    mu_left_right = mu_left * mu_right
    sigma_left_sq = _blur(left * left, kernel) - mu_left_sq
    sigma_right_sq = _blur(right * right, kernel) - mu_right_sq
    sigma_left_right = _blur(left * right, kernel) - mu_left_right
    numerator = (2.0 * mu_left_right + c1) * (2.0 * sigma_left_right + c2)
    denominator = (mu_left_sq + mu_right_sq + c1) * (sigma_left_sq + sigma_right_sq + c2)
    return float(np.mean(numerator / denominator))
