"""Tests for canonical Stage 2 results consolidation."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

import scripts.consolidate_stage2_results as consolidate


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_validate_rejects_result_that_differs_from_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = {
        "job_id": "splat_eval_run_p000",
        "dataset": "dataset1",
        "training_resolution": "2048",
        "patch_size": "200",
        "splat_count": "2000000",
        "status": "complete",
        "ssim": "0.7",
        "psnr": "22",
        "lpips": "0.3",
        "actual_splat_count": "2000000",
    }
    source = tmp_path / "raw.csv"
    _write(source, [raw])
    monkeypatch.setattr(consolidate, "ROOT", tmp_path)
    row = {
        "dataset_id": "D1",
        "dataset": "dataset1",
        "training_resolution": "2048",
        "patch_size": "200",
        "gaussian_limit": "2000000",
        "patch_id": "p000",
        "run_id": "run",
        "outer_run_id": "outer",
        "status": "COMPLETE",
        "ssim": "0.7",
        "psnr": "23",
        "lpips": "0.3",
        "actual_splat_count": "2000000",
        "source_uri": "s3://example/raw.csv",
    }
    inventory = [{"source_uri": row["source_uri"], "local_path": "raw.csv"}]

    with pytest.raises(ValueError, match="psnr differs"):
        consolidate.validate([row], inventory)
