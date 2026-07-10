"""Tests for Stage 2 probe completion validation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from reefs.experiments.ablations.probe_validation import validate_probe_outputs


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _complete_probe(tmp_path: Path) -> tuple[Path, str]:
    output = tmp_path / "ablation_eval"
    probe = "splat_dataset1_sfm_1024_sift_global_res1024_patch400_500k"
    row_id = f"splat_eval_{probe}_p000"
    _write_csv(
        output / "results_splat.csv",
        ["job_id", "patch_id", "status"],
        [{"job_id": row_id, "patch_id": "p000", "status": "complete"}],
    )
    _write_csv(
        output / "metrics_long.csv",
        ["job_id", "iteration", "psnr"],
        [{"job_id": row_id, "iteration": 30000, "psnr": 22.0}],
    )
    manifest = output / "eval_datasets" / probe / "p000" / "eval_dataset_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "target_image_source": "full_resolution_undistorted",
                "requested_training_resolution": "1024",
                "uses_mixed_resolution_sources": True,
            }
        ),
        encoding="utf-8",
    )
    attempt = output / "splat_eval" / probe / "p000" / "attempt_1"
    attempt.mkdir(parents=True)
    splat = attempt / "splat_finished.ply"
    splat.write_text("ply\n", encoding="utf-8")
    (attempt / "training_status.json").write_text(
        json.dumps({"output_file": str(splat)}) + "\n",
        encoding="utf-8",
    )
    comparisons = attempt / "eval_step_30000"
    comparisons.mkdir()
    (comparisons / "comparison.png").write_bytes(b"png")
    return output, probe


def test_stage2_probe_completion_requires_all_final_evidence(tmp_path: Path) -> None:
    output, probe = _complete_probe(tmp_path)

    completion = validate_probe_outputs(
        output_root=output,
        probe_id=probe,
        expected_patch_ids=["p000"],
        training_resolution="1024",
    )

    assert completion["status"] == "complete_local_verified"
    assert (output / "probe_manifests" / probe / "probe_complete.json").is_file()


def test_stage2_probe_completion_rejects_missing_final_metrics(tmp_path: Path) -> None:
    output, probe = _complete_probe(tmp_path)
    metrics = output / "metrics_long.csv"
    metrics.write_text(metrics.read_text(encoding="utf-8").replace("30000", "15000"), encoding="utf-8")

    with pytest.raises(ValueError, match="30000-iteration metrics"):
        validate_probe_outputs(
            output_root=output,
            probe_id=probe,
            expected_patch_ids=["p000"],
            training_resolution="1024",
        )
