"""Tests for post-processing artefact discovery."""

from __future__ import annotations

from pathlib import Path

from reefs.io.yaml_json import write_json
from reefs.postprocess.artifacts import (
    cleaned_output_for,
    discover_patch_training_sources,
    ply_vertex_count,
)


def _write_ply(path: Path, vertices: int = 3) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"ply\nformat ascii 1.0\nelement vertex {vertices}\nproperty float x\nend_header\n",
        encoding="utf-8",
    )
    return path


def test_discover_patch_training_sources_prefers_finished(tmp_path: Path) -> None:
    patch = tmp_path / "p000" / "splat"
    _write_ply(patch / "splat_100.ply")
    finished = _write_ply(patch / "splat_finished.ply")
    write_json(
        tmp_path / "p000" / "splat" / "training_status.json",
        {"requested_iterations": 100, "completed_iterations": 100, "status": "complete"},
    )

    sources = discover_patch_training_sources(patches_dir=tmp_path)

    assert sources[0].source_file == finished
    assert sources[0].source_kind == "finished"
    assert sources[0].severity == "normal"


def test_discover_patch_training_sources_uses_highest_iteration_and_threshold(tmp_path: Path) -> None:
    patch = tmp_path / "p001" / "splat"
    _write_ply(patch / "splat_100.ply")
    chosen = _write_ply(patch / "splat_850.ply")
    write_json(
        patch / "training_status.json",
        {"requested_iterations": 1000, "completed_iterations": 850, "status": "warning"},
    )

    sources = discover_patch_training_sources(patches_dir=tmp_path, severe_threshold=0.8)

    assert sources[0].source_file == chosen
    assert sources[0].severity == "warning"
    assert sources[0].completion_ratio == 0.85


def test_discover_patch_training_sources_marks_missing_output_failed(tmp_path: Path) -> None:
    (tmp_path / "p002" / "splat").mkdir(parents=True)

    sources = discover_patch_training_sources(patches_dir=tmp_path)

    assert sources[0].usable is False
    assert sources[0].severity == "failed"


def test_ply_vertex_count_and_cleaned_output_name(tmp_path: Path) -> None:
    source = _write_ply(tmp_path / "splat_100_clean_input.ply", vertices=42)

    assert ply_vertex_count(source) == 42
    assert cleaned_output_for(source).name == "splat_100_clean_input_clean.ply"
