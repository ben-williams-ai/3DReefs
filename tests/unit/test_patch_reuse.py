"""Tests for patch reuse and patch-affecting config comparison."""

from __future__ import annotations

from pathlib import Path

from reefs.config.models import PipelineConfig
from reefs.io.yaml_json import write_json
from reefs.runs.manifest import create_run_paths
from reefs.splat.resume import diff_patch_affecting_config, inspect_patch_affecting_config_changes
from reefs.splat.validation import create_splat_paths


def test_diff_patch_affecting_config_reports_dotted_paths() -> None:
    differences = diff_patch_affecting_config(
        {"patching": {"max_cameras": 100}},
        {"patching": {"max_cameras": 200}},
    )

    assert differences == [{"path": "patching.max_cameras", "previous_value": 100, "requested_value": 200}]


def test_inspect_patch_affecting_config_changes_reads_existing_metadata(tmp_path: Path) -> None:
    run_paths = create_run_paths(tmp_path / "runs")
    paths = create_splat_paths(run_paths)
    patch = paths.patches / "p000"
    patch.mkdir(parents=True)
    write_json(
        patch / "patch_metadata.json",
        {
            "patch_id": "p000",
            "patch_affecting_config": {"patching": {"max_cameras": 100}},
        },
    )
    config = PipelineConfig.model_validate(
        {
            "project": {"dir": str(tmp_path)},
            "tools": {},
            "advanced": {"splat": {"patching": {"max_cameras": 200}}},
        }
    )

    changes = inspect_patch_affecting_config_changes(paths, config)

    assert changes[0]["patch_id"] == "p000"
    assert changes[0]["differences"]
