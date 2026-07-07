"""Tests for Python-owned eval image metrics."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from PIL import Image

from reefs.eval.image_metrics import write_python_eval_metrics


def _comparison(path: Path, *, gt: tuple[int, int, int], rendered: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (12, 4))
    image.paste(Image.new("RGB", (4, 4), gt), (0, 0))
    image.paste(Image.new("RGB", (4, 4), rendered), (8, 0))
    image.save(path)


def test_python_metrics_write_canonical_csv_and_delete_lfs_metrics(tmp_path: Path) -> None:
    output = tmp_path / "attempt"
    _comparison(output / "eval_step_500" / "0.png", gt=(0, 0, 0), rendered=(0, 0, 0))
    metrics = output / "metrics.csv"
    metrics.write_text("iteration,psnr,ssim\n500,999,0.99\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "target_image_source": "full_resolution_undistorted",
                "holdout_image_dimensions": {"a.jpg": {"width": 4, "height": 4}},
            }
        ),
        encoding="utf-8",
    )

    final, rows = write_python_eval_metrics(
        output_dir=output,
        metrics_path=metrics,
        iterations=[500],
        compute_lpips=False,
        num_gaussians=42,
        expected_manifest=manifest,
    )

    assert math.isinf(float(final["psnr"]))
    assert final["ssim"] == 1.0
    assert final["metric_source"] == "python_full_resolution_undistorted"
    assert rows == [final]
    text = metrics.read_text(encoding="utf-8")
    assert "999" not in text
    assert "python_full_resolution_undistorted" in text
    with metrics.open(newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle))[0]["num_gaussians"] == "42"


def test_python_metrics_detect_known_difference(tmp_path: Path) -> None:
    output = tmp_path / "attempt"
    _comparison(output / "eval_step_500" / "0.png", gt=(0, 0, 0), rendered=(255, 255, 255))

    final, _ = write_python_eval_metrics(
        output_dir=output,
        metrics_path=output / "metrics.csv",
        iterations=[500],
        compute_lpips=False,
        num_gaussians=None,
    )

    assert final["psnr"] == 0.0
    assert float(final["ssim"]) < 0.01


def test_python_metrics_reject_malformed_comparison(tmp_path: Path) -> None:
    output = tmp_path / "attempt"
    malformed = output / "eval_step_500" / "0.png"
    malformed.parent.mkdir(parents=True)
    Image.new("RGB", (9, 4)).save(malformed)

    try:
        write_python_eval_metrics(
            output_dir=output,
            metrics_path=output / "metrics.csv",
            iterations=[500],
            compute_lpips=False,
            num_gaussians=None,
        )
    except ValueError as exc:
        assert "unexpected LFS eval image shape" in str(exc)
    else:
        raise AssertionError("expected malformed comparison image to fail")
