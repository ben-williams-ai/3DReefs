"""Tests for patch reuse and patch-affecting config comparison."""

from __future__ import annotations

from pathlib import Path

from reefs.config.models import PipelineConfig
from reefs.io.yaml_json import write_json
from reefs.patches.selection import SELECTOR_NAME
from reefs.runs.manifest import create_run_paths
from reefs.splat.resume import (
    diff_patch_affecting_config,
    inspect_patch_affecting_config_changes,
    materialise_patch_affecting_config,
)
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


def test_materialise_patch_affecting_config_includes_selector_provenance(tmp_path: Path) -> None:
    config = PipelineConfig.model_validate(
        {
            "project": {"dir": str(tmp_path)},
            "tools": {},
            "advanced": {"splat": {"patching": {"max_cameras": 800}}},
        }
    )

    patch_config = materialise_patch_affecting_config(config)

    assert patch_config["selector"]["name"] == SELECTOR_NAME


def test_inspect_patch_affecting_config_changes_flags_legacy_selector_metadata(tmp_path: Path) -> None:
    run_paths = create_run_paths(tmp_path / "runs")
    paths = create_splat_paths(run_paths)
    patch = paths.patches / "p000"
    patch.mkdir(parents=True)
    write_json(
        patch / "patch_metadata.json",
        {
            "patch_id": "p000",
            "patch_affecting_config": {
                "patching": {"max_cameras": 800},
                "selector": {"name": "old_boundary_first"},
            },
        },
    )
    config = PipelineConfig.model_validate(
        {
            "project": {"dir": str(tmp_path)},
            "tools": {},
            "advanced": {"splat": {"patching": {"max_cameras": 800}}},
        }
    )

    changes = inspect_patch_affecting_config_changes(paths, config)

    assert changes[0]["patch_id"] == "p000"
    assert any(item["path"] == "selector.name" for item in changes[0]["differences"])
