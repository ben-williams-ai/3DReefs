"""Tests for ablation splat eval continuation helpers."""

from __future__ import annotations

from pathlib import Path

from reefs.experiments.ablations.config import AblationConfig, DatasetSpec, SfMVariant
from reefs.experiments.ablations.grid import SfMJob
from reefs.experiments.ablations.splat_eval import (
    _clean_sfm_jobs,
    _next_attempt_dir,
    _shared_patch_ids_by_dataset,
)
from reefs.experiments.ablations.ledger import SFM_FIELDS, atomic_write_csv


def _config(tmp_path: Path) -> AblationConfig:
    return AblationConfig(
        output_root=tmp_path / "ablations",
        datasets=[],
        sfm_variants=[],
        patch_sizes=[400],
        splat_counts=[2_000_000],
        max_widths=[4096],
        validation_patch_count=5,
        holdout_fraction=0.1,
        sfm_timeout_hours=20,
        default_patch_size=400,
        default_splat_count=2_000_000,
        lfs_eval_every_iterations=1000,
        run_validation_splats_for_sfm=False,
    )


def _job(tmp_path: Path, *, variant: str) -> SfMJob:
    return SfMJob(
        dataset=DatasetSpec(
            name="dataset1",
            config=tmp_path / "dataset.yml",
            project_dir=tmp_path / "dataset1",
        ),
        variant=SfMVariant(name=variant, description=variant),
        patch_size=400,
        splat_count=2_000_000,
    )


def _patches(job: SfMJob, patch_ids: list[str]) -> None:
    patches_dir = job.dataset.project_dir / "runs" / job.job_id / "splat" / "patches"
    for patch_id in patch_ids:
        (patches_dir / patch_id).mkdir(parents=True)


def test_clean_sfm_jobs_uses_only_successful_rows(tmp_path: Path) -> None:
    config = _config(tmp_path)
    good = _job(tmp_path, variant="good")
    warning = _job(tmp_path, variant="warning")
    atomic_write_csv(
        config.output_root / "results_sfm.csv",
        SFM_FIELDS,
        [
            {"job_id": good.job_id, "status": "complete"},
            {"job_id": warning.job_id, "status": "complete_with_warnings"},
        ],
    )

    assert _clean_sfm_jobs(config=config, jobs=[good, warning]) == [good]


def test_shared_patch_ids_use_dataset_intersection(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = _job(tmp_path, variant="first")
    second = _job(tmp_path, variant="second")
    _patches(first, [f"p{index:03d}" for index in range(20)])
    _patches(second, [f"p{index:03d}" for index in range(2, 22)])

    assert _shared_patch_ids_by_dataset(config=config, jobs=[first, second]) == {
        "dataset1": ["p002", "p006", "p010", "p015", "p019"]
    }


def test_next_attempt_dir_preserves_existing_attempts(tmp_path: Path) -> None:
    (tmp_path / "attempt_1").mkdir()
    (tmp_path / "attempt_2").mkdir()

    assert _next_attempt_dir(tmp_path) == tmp_path / "attempt_3"
