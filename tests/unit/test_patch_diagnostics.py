"""Tests for patch diagnostic artefacts."""

from __future__ import annotations

from pathlib import Path
import csv

from reefs.diagnostics.patch_plots import write_patch_selection_diagnostics, write_patch_summary
from reefs.patches.artefacts import read_sparse_scene_text
from reefs.patches.bounds import PatchBounds
from reefs.patches.selection import select_patch_views
from tests.conftest import write_sparse_text_model


def test_write_patch_selection_diagnostics_creates_required_files(tmp_path: Path) -> None:
    source_sparse = write_sparse_text_model(tmp_path / "sparse", ["image_0001.jpg"])
    scene = read_sparse_scene_text(source_sparse)
    selection = select_patch_views(scene, PatchBounds("p000", -1, 1, -1, 1, 0, 5, 0.1), max_cameras=10)

    warnings = write_patch_selection_diagnostics(selection, tmp_path / "diagnostics")

    assert warnings == []
    assert (tmp_path / "diagnostics" / "camera_coverage.csv").exists()
    assert (tmp_path / "diagnostics" / "generation.log").exists()
    assert (tmp_path / "diagnostics" / "plot.html").exists()
    assert (tmp_path / "diagnostics" / "plot.png").exists()
    assert (tmp_path / "diagnostics" / "histogram.png").exists()
    with (tmp_path / "diagnostics" / "camera_coverage.csv").open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert "target_image_share" in row
    assert "footprint_overlap_score" in row
    log_text = (tmp_path / "diagnostics" / "generation.log").read_text(encoding="utf-8")
    assert "selected_internal_count:" in log_text
    assert "selected_external_count:" in log_text


def test_write_patch_summary_creates_run_level_plot(tmp_path: Path) -> None:
    source_sparse = write_sparse_text_model(tmp_path / "sparse", ["cam1/image_0001.jpg", "cam2/image_0002.jpg"])
    scene = read_sparse_scene_text(source_sparse)
    bounds = [
        PatchBounds("p000", -1, 1, -1, 1, 0, 5, 0.1),
        PatchBounds("p001", 1, 3, -1, 1, 0, 5, 0.1),
    ]

    warnings = write_patch_summary(scene, bounds, tmp_path / "patch_summary.png")

    assert warnings == []
    assert (tmp_path / "patch_summary.png").exists()
