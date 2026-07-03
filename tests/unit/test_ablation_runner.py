"""Tests for ablation runner smoke output."""

from __future__ import annotations

from pathlib import Path

from reefs.experiments.ablations.config import AblationConfig, DatasetSpec, SfMVariant
from reefs.experiments.ablations.ledger import SPLAT_FIELDS, read_rows
from reefs.experiments.ablations.runner import _stage_completed, run_splat_grid_job, smoke


def test_smoke_simulation_writes_preview_outputs(tmp_path: Path) -> None:
    config = AblationConfig(
        output_root=tmp_path / "ablations",
        datasets=[
            DatasetSpec(
                name="dataset1",
                config=Path("configs/datasets/dataset_01.yml"),
                project_dir=Path("data/dataset1"),
            )
        ],
        sfm_variants=[SfMVariant(name="baseline", description="baseline")],
        aims_baseline_overrides={},
        patch_sizes=[400],
        splat_counts=[2_000_000],
        max_widths=[4096],
        validation_patch_count=5,
        holdout_fraction=0.1,
        sfm_timeout_hours=20,
        default_patch_size=400,
        default_splat_count=2_000_000,
        run_validation_splats_for_sfm=True,
    )

    smoke(config=config, simulate=True)

    preview = config.output_root / "smoke_preview"
    assert (preview / "plan.md").exists()
    assert (preview / "progress.md").exists()
    assert (preview / "manifest.csv").exists()
    assert (preview / "results_sfm.csv").exists()
    assert (preview / "results_splat.csv").exists()
    assert (
        preview / "holdouts" / "dataset1" / "sfm_dataset1_sfm_baseline" / "patch400" / "p000.json"
    ).exists()


def test_stage2_simulation_writes_results_splat_schema(tmp_path: Path) -> None:
    config = AblationConfig(
        output_root=tmp_path / "ablations",
        datasets=[
            DatasetSpec(
                name="dataset1",
                config=Path("configs/datasets/dataset_01.yml"),
                project_dir=tmp_path / "dataset1",
            )
        ],
        sfm_variants=[SfMVariant(name="sfm_baseline", description="baseline")],
        aims_baseline_overrides={},
        patch_sizes=[400],
        splat_counts=[2_000_000],
        max_widths=[],
        validation_patch_count=2,
        holdout_fraction=0.1,
        sfm_timeout_hours=20,
        default_patch_size=400,
        default_splat_count=2_000_000,
        run_validation_splats_for_sfm=True,
    )

    run_splat_grid_job(
        config=config,
        job_id="splat_dataset1_best_patch400_2m",
        source_sfm_variant="sfm_baseline",
        simulate=True,
        force_jobs=set(),
    )

    rows = read_rows(config.output_root / "results_splat.csv")
    assert list(rows[0]) == SPLAT_FIELDS
    assert rows[0]["job_id"] == "splat_eval_splat_dataset1_best_patch400_2m_p000"
    assert rows[0]["patch_size"] == "400"
    assert rows[0]["splat_count"] == "2000000"


def test_stage_completed_requires_matching_run_status(tmp_path: Path) -> None:
    status = tmp_path / "run_status.json"

    assert not _stage_completed(status, "splat.patch")
    status.write_text('{"stage_statuses":{"splat.preflight":"complete"}}', encoding="utf-8")
    assert not _stage_completed(status, "splat.patch")
    status.write_text('{"stage_statuses":{"splat.patch":"complete"}}', encoding="utf-8")
    assert _stage_completed(status, "splat.patch")
