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


def test_upsert_row_backs_up_completed_row_before_replacement(tmp_path: Path) -> None:
    path = tmp_path / "results.csv"
    fields = ["job_id", "status", "value"]

    upsert_row(path, fields, {"job_id": "a", "status": "complete", "value": "1"})
    upsert_row(path, fields, {"job_id": "a", "status": "complete", "value": "2"})

    backups = list((tmp_path / "ledger_backups").glob("results_a_*.csv"))
    assert len(backups) == 1
    assert read_rows(backups[0]) == [{"job_id": "a", "status": "complete", "value": "1"}]
    assert read_rows(path) == [{"job_id": "a", "status": "complete", "value": "2"}]


def test_upsert_row_rejects_unknown_status(tmp_path: Path) -> None:
    path = tmp_path / "results.csv"

    try:
        upsert_row(path, ["job_id", "status"], {"job_id": "a", "status": "done"})
    except ValueError as exc:
        assert "unknown ablation status: done" in str(exc)
    else:
        raise AssertionError("expected ValueError")
