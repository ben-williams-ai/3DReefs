"""Tests for patch diagnostic artefacts."""

from __future__ import annotations

from pathlib import Path

from reefs.diagnostics.patch_plots import write_patch_selection_diagnostics
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
    assert (tmp_path / "diagnostics" / "selection_plot.png").exists()
    assert (tmp_path / "diagnostics" / "coverage_histogram.png").exists()
