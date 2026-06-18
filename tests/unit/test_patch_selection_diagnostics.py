"""Tests for target-aware patch selection diagnostics."""

from __future__ import annotations

import csv
from pathlib import Path

from reefs.diagnostics.patch_plots import write_patch_selection_diagnostics
from reefs.patches.selection import select_patch_views
from tests.fixtures.patch_selection import bounds, image, point, scene


def test_camera_coverage_csv_uses_target_aware_contract(tmp_path: Path) -> None:
    sparse_scene = scene(tmp_path, [image(1, "image.jpg", center=(0, 0, 0))], [point(1, (0, 0, 4), (1,))])
    selection = select_patch_views(sparse_scene, bounds(), max_cameras=10)

    warnings = write_patch_selection_diagnostics(selection, tmp_path / "diagnostics")

    assert warnings == []
    rows = list(csv.DictReader((tmp_path / "diagnostics" / "camera_coverage.csv").open()))
    assert rows
    assert rows[0]["patch_id"] == "p000"
    assert rows[0]["camera_role"] == "internal"
    assert "matched_track_score" in rows[0]
    assert "geometric_visibility_score" in rows[0]
    assert "target_image_share" in rows[0]
    assert "warning_flags" in rows[0]


def test_generation_log_records_selector_thresholds(tmp_path: Path) -> None:
    sparse_scene = scene(tmp_path, [image(1, "image.jpg", center=(0, 0, 0))], [point(1, (0, 0, 4), (1,))])
    selection = select_patch_views(sparse_scene, bounds(), max_cameras=10)

    write_patch_selection_diagnostics(selection, tmp_path / "diagnostics")

    log_text = (tmp_path / "diagnostics" / "generation.log").read_text(encoding="utf-8")
    assert "selector_name: camera_selection_v2" in log_text
    assert "footprint_coverage:" in log_text
    assert "warning_thresholds:" in log_text
