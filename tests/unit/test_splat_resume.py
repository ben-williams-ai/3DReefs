"""Tests for splat existing-output discovery."""

from __future__ import annotations

from reefs.runs.manifest import create_run_paths
from reefs.splat.resume import discover_existing_splat_outputs
from reefs.splat.validation import create_splat_paths


def test_discover_existing_splat_outputs_finds_patch_local_training_outputs(tmp_path) -> None:
    run_paths = create_run_paths(tmp_path / "runs")
    paths = create_splat_paths(run_paths)
    patch_splat = paths.patches / "p000" / "splat"
    patch_splat.mkdir(parents=True)
    (patch_splat / "training_status.json").write_text("{}", encoding="utf-8")

    outputs = discover_existing_splat_outputs(paths, ["splat.train"])

    assert len(outputs) == 1
    assert outputs[0].stage == "splat.train"
    assert outputs[0].path == patch_splat
