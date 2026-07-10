"""Completion checks for one Stage 2 scientific probe."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def validate_probe_outputs(
    *,
    output_root: Path,
    probe_id: str,
    expected_patch_ids: list[str],
    training_resolution: str,
) -> dict[str, object]:
    """Fail unless every expected patch has final mixed-resolution evidence."""
    result_rows = _csv_rows(output_root / "results_splat.csv")
    rows = [row for row in result_rows if row.get("job_id", "").startswith(f"splat_eval_{probe_id}_")]
    observed = sorted(row.get("patch_id", "") for row in rows)
    if observed != sorted(expected_patch_ids):
        raise ValueError(f"probe {probe_id} patch rows differ: {observed} != {sorted(expected_patch_ids)}")
    failures = [row for row in rows if not row.get("status", "").startswith("complete")]
    if failures:
        raise ValueError(f"probe {probe_id} has {len(failures)} incomplete patch row(s)")

    metrics = _csv_rows(output_root / "metrics_long.csv")
    for patch_id in expected_patch_ids:
        patch_metrics = [
            row
            for row in metrics
            if row.get("job_id") == f"splat_eval_{probe_id}_{patch_id}" and row.get("iteration") == "30000"
        ]
        if not patch_metrics:
            raise ValueError(f"probe {probe_id}/{patch_id} has no final 30000-iteration metrics")
        manifest_path = output_root / "eval_datasets" / probe_id / patch_id / "eval_dataset_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("target_image_source") != "full_resolution_undistorted":
            raise ValueError(f"probe {probe_id}/{patch_id} did not use full-resolution evaluation")
        if manifest.get("requested_training_resolution") != training_resolution:
            raise ValueError(f"probe {probe_id}/{patch_id} records the wrong training resolution")
        if training_resolution != "full" and not manifest.get("uses_mixed_resolution_sources"):
            raise ValueError(f"probe {probe_id}/{patch_id} did not use mixed-resolution sources")
        attempts = sorted((output_root / "splat_eval" / probe_id / patch_id).glob("attempt_*"))
        if not attempts or not (attempts[-1] / "training_status.json").is_file():
            raise ValueError(f"probe {probe_id}/{patch_id} has no final training status")
        status = json.loads((attempts[-1] / "training_status.json").read_text(encoding="utf-8"))
        output_file = Path(str(status.get("output_file", "")))
        if not output_file.is_file():
            raise ValueError(f"probe {probe_id}/{patch_id} has no final splat output")
        if not list((attempts[-1] / "eval_step_30000").glob("*.png")):
            raise ValueError(f"probe {probe_id}/{patch_id} has no final comparison images")

    completion = {
        "status": "complete_local_verified",
        "probe_id": probe_id,
        "training_resolution": training_resolution,
        "expected_patch_ids": expected_patch_ids,
        "patch_count": len(expected_patch_ids),
        "final_iteration": 30000,
    }
    target = output_root / "probe_manifests" / probe_id / "probe_complete.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(completion, indent=2) + "\n", encoding="utf-8")
    return completion


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"missing Stage 2 result ledger: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
