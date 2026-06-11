"""Tests for LichtFeld Studio progress and status parsing."""

from __future__ import annotations

from pathlib import Path

from reefs.lfs.status import classify_lfs_status, parse_lfs_progress_lines


def test_parse_lfs_progress_lines() -> None:
    progress = parse_lfs_progress_lines(["100/500 | Loss: 1.2e-3 | Splats: 12345"])

    assert progress[0].completed_iterations == 100
    assert progress[0].requested_iterations == 500
    assert progress[0].loss == 1.2e-3
    assert progress[0].splats == 12345


def test_classify_complete_training(tmp_path: Path) -> None:
    (tmp_path / "p000_splat_500.ply").write_text("ply", encoding="utf-8")
    progress = parse_lfs_progress_lines(["500/500 | Loss: 0.1 | Splats: 99"])

    status = classify_lfs_status(
        patch_id="p000",
        requested_iterations=500,
        return_code=0,
        output_dir=tmp_path,
        progress=progress,
        severe_completion_threshold=0.8,
    )

    assert status["status"] == "complete"
    assert status["completion_ratio"] == 1.0


def test_classify_complete_training_uses_successful_output_iteration(tmp_path: Path) -> None:
    (tmp_path / "splat_30000.ply").write_text("ply", encoding="utf-8")
    progress = parse_lfs_progress_lines(["29900/30000 | Loss: 0.1 | Splats: 1500000"])

    status = classify_lfs_status(
        patch_id="p000",
        requested_iterations=30000,
        return_code=0,
        output_dir=tmp_path,
        progress=progress,
        severe_completion_threshold=0.8,
    )

    assert status["status"] == "complete"
    assert status["completed_iterations"] == 30000
    assert status["completion_ratio"] == 1.0


def test_classify_partial_training_warning(tmp_path: Path) -> None:
    (tmp_path / "p000_splat_450.ply").write_text("ply", encoding="utf-8")
    progress = parse_lfs_progress_lines(["450/500 | Loss: 0.1 | Splats: 99"])

    status = classify_lfs_status(
        patch_id="p000",
        requested_iterations=500,
        return_code=1,
        output_dir=tmp_path,
        progress=progress,
        severe_completion_threshold=0.8,
    )

    assert status["status"] == "warning"
