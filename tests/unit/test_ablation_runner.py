"""Tests for ablation runner smoke output."""

from __future__ import annotations

from pathlib import Path

from reefs.experiments.ablations.config import AblationConfig, DatasetSpec, SfMVariant
from reefs.experiments.ablations.runner import smoke


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
        patch_sizes=[400],
        splat_counts=[2_000_000],
        max_widths=[4096],
        validation_patch_count=5,
        holdout_fraction=0.1,
        sfm_timeout_hours=20,
        default_patch_size=400,
        default_splat_count=2_000_000,
        lfs_eval_every_iterations=1000,
        run_validation_splats_for_sfm=True,
    )

    smoke(config=config, simulate=True)

    preview = config.output_root / "smoke_preview"
    assert (preview / "plan.md").exists()
    assert (preview / "progress.md").exists()
    assert (preview / "manifest.csv").exists()
    assert (preview / "results_sfm.csv").exists()
    assert (preview / "results_splat.csv").exists()
    assert (preview / "holdouts" / "dataset1" / "patch400" / "p000.json").exists()
