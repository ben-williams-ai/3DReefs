"""Tests for LPIPS post-processing of LFS eval images."""

from __future__ import annotations

from pathlib import Path

import torch
from PIL import Image

from reefs.eval.lpips import add_lpips_to_lfs_metrics


class _ConstantLpips:
    def eval(self):
        return self

    def __call__(self, gt: torch.Tensor, rendered: torch.Tensor) -> torch.Tensor:
        return torch.tensor([float(torch.mean(torch.abs(gt - rendered)))])


def test_add_lpips_to_lfs_metrics_splits_lfs_composites(tmp_path: Path) -> None:
    output_dir = tmp_path / "attempt"
    eval_dir = output_dir / "eval_step_500"
    eval_dir.mkdir(parents=True)
    composite = Image.new("RGB", (12, 4), color=(0, 0, 0))
    gt = Image.new("RGB", (4, 4), color=(0, 0, 0))
    rendered = Image.new("RGB", (4, 4), color=(255, 255, 255))
    composite.paste(gt, (0, 0))
    composite.paste(rendered, (8, 0))
    composite.save(eval_dir / "0.png")
    metrics_path = output_dir / "metrics.csv"
    metrics_path.write_text(
        "iteration,psnr,ssim,time_per_image,num_gaussians\n"
        "500,10.0,0.2,0.01,42\n",
        encoding="utf-8",
    )

    values = add_lpips_to_lfs_metrics(
        output_dir=output_dir,
        metrics_path=metrics_path,
        iterations=[500],
        model_factory=lambda _device: _ConstantLpips(),
    )

    assert values[500] == 2.0
    text = metrics_path.read_text(encoding="utf-8")
    assert "iteration,psnr,ssim,lpips,time_per_image,num_gaussians" in text
    assert "500,10.0,0.2,2.000000,0.01,42" in text


def test_add_lpips_to_lfs_metrics_is_noop_without_saved_images(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.csv"
    metrics_path.write_text(
        "iteration,psnr,ssim,time_per_image,num_gaussians\n"
        "500,10.0,0.2,0.01,42\n",
        encoding="utf-8",
    )

    values = add_lpips_to_lfs_metrics(output_dir=tmp_path, metrics_path=metrics_path, iterations=[500])

    assert values == {}
    assert "lpips" not in metrics_path.read_text(encoding="utf-8")
