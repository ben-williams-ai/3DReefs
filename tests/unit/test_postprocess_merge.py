"""Tests for cleaned patch merge helpers."""

from __future__ import annotations

import sys
import types
from pathlib import Path

from reefs.config.models import SplatMergeConfig
from reefs.postprocess.artifacts import CleanupRecord, PatchTrainingSource
from reefs.postprocess.merge import build_merge_inputs, build_merge_params, run_merge


def _source(tmp_path: Path, patch_id: str, severity: str = "normal") -> PatchTrainingSource:
    return PatchTrainingSource(
        patch_id=patch_id,
        patch_dir=tmp_path / patch_id,
        source_file=tmp_path / patch_id / "splat" / "splat_finished.ply",
        source_kind="finished",
        requested_iterations=100,
        completed_iterations=100,
        completion_ratio=1.0,
        severity=severity,
        usable=True,
        reason="completed_training_output",
    )


def _cleanup_record(tmp_path: Path, patch_id: str, *, status: str = "complete", severity: str = "normal") -> CleanupRecord:
    cleaned = tmp_path / patch_id / "splat" / "splat_finished_clean.ply"
    if status == "complete":
        cleaned.parent.mkdir(parents=True, exist_ok=True)
        cleaned.write_text("ply\n", encoding="utf-8")
    return CleanupRecord(
        patch_id=patch_id,
        source=_source(tmp_path, patch_id, severity),
        output_file=cleaned,
        status=status,
        cleanup_settings={},
    )


def test_build_merge_inputs_records_included_and_excluded(tmp_path: Path) -> None:
    records = [
        _cleanup_record(tmp_path, "p000"),
        _cleanup_record(tmp_path, "p001", status="failed", severity="severe_warning"),
    ]

    inputs = build_merge_inputs(cleanup_records=records, config=SplatMergeConfig())

    assert inputs[0].included is True
    assert inputs[1].included is False
    assert inputs[1].source_severity == "severe_warning"


def test_build_merge_params_use_wildflow_shape(tmp_path: Path) -> None:
    params = build_merge_params([tmp_path / "a.ply", tmp_path / "b.ply"], tmp_path / "merged.ply")

    assert params == {
        "input_files": [str(tmp_path / "a.ply"), str(tmp_path / "b.ply")],
        "output_file": str(tmp_path / "merged.ply"),
    }


def test_run_merge_uses_wildflow(tmp_path: Path, monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    wildflow = types.ModuleType("wildflow")
    splat = types.ModuleType("wildflow.splat")

    def merge_ply_files(params: dict[str, object]) -> None:
        calls.append(params)
        Path(str(params["output_file"])).write_text("ply\n", encoding="utf-8")

    splat.merge_ply_files = merge_ply_files
    splat.cleanup_splats = lambda _params: None
    wildflow.splat = splat
    monkeypatch.setitem(sys.modules, "wildflow", wildflow)
    monkeypatch.setitem(sys.modules, "wildflow.splat", splat)
    records = [_cleanup_record(tmp_path, "p000")]

    status = run_merge(
        cleanup_records=records,
        config=SplatMergeConfig(),
        output_file=tmp_path / "merged.ply",
    )

    assert status.status == "complete"
    assert calls[0]["output_file"] == str(tmp_path / "merged.ply")
