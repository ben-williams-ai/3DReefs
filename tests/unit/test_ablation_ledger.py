"""Tests for ablation CSV ledgers."""

from __future__ import annotations

from pathlib import Path

from reefs.experiments.ablations.ledger import read_rows, upsert_row


def test_upsert_row_replaces_by_job_id(tmp_path: Path) -> None:
    path = tmp_path / "results.csv"
    fields = ["job_id", "status", "value"]

    upsert_row(path, fields, {"job_id": "a", "status": "failed", "value": "1"})
    upsert_row(path, fields, {"job_id": "a", "status": "complete", "value": "2"})

    assert read_rows(path) == [{"job_id": "a", "status": "complete", "value": "2"}]
