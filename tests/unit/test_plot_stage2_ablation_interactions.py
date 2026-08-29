"""Tests for Stage 2 interaction-plot completion markers."""

from __future__ import annotations

import csv

import scripts.figure_creation.plot_stage2_ablation_interactions as plotting


def test_undertrained_config_uses_strict_90_percent_threshold(
    tmp_path, monkeypatch
) -> None:
    rows = []
    for dataset, complete, attempted in (
        ("D3", 0, 4),
        ("D4", 9, 10),
        ("D5", 8, 10),
    ):
        rows.extend(
            {
                "dataset_id": dataset,
                "training_resolution": "full",
                "patch_size": "800",
                "gaussian_limit": "2000000",
                "status": "COMPLETE" if index < complete else "FAILED",
            }
            for index in range(attempted)
        )
    audit = tmp_path / "all.csv"
    with audit.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    monkeypatch.setattr(plotting, "AUDIT_INPUT", audit)

    assert plotting.load_undertrained_configs() == {("full", "800", "2000000")}
