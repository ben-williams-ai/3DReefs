"""Tests for ablation splat eval continuation helpers."""

from __future__ import annotations

from pathlib import Path

from reefs.experiments.ablations.config import AblationConfig, DatasetSpec, SfMVariant
from reefs.experiments.ablations.grid import SfMJob
from reefs.experiments.ablations.holdout import select_holdout
from reefs.experiments.ablations.splat_eval import (
    _clean_sfm_jobs,
    _is_retryable_width_failure,
    _next_attempt_dir,
    _patch_ids_by_job,
    _patch_tasks,
)
from reefs.experiments.ablations.ledger import SFM_FIELDS, atomic_write_csv


def _config(tmp_path: Path, *, patch_count: int = 10) -> AblationConfig:
    return AblationConfig(
        output_root=tmp_path / "ablations",
        datasets=[],
        sfm_variants=[],
        patch_sizes=[400],
        splat_counts=[2_000_000],
        max_widths=[4096],
        validation_patch_count=patch_count,
        holdout_fraction=0.1,
        sfm_timeout_hours=20,
        default_patch_size=400,
        default_splat_count=2_000_000,
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


def _minimal_patch(tmp_path: Path) -> Path:
    patch_dir = tmp_path / "patch"
    (patch_dir / "sparse" / "0").mkdir(parents=True)
    (patch_dir / "patch_metadata.json").write_text(
        '{"patch_id":"p000","selected_images":["a.jpg","b.jpg","c.jpg","d.jpg"],"selected_internal_count":4}',
        encoding="utf-8",
    )
    (patch_dir / "sparse" / "0" / "images.txt").write_text(
        "1 1 0 0 0 0 0 0 1 a.jpg\n\n"
        "2 1 0 0 0 0 0 0 1 b.jpg\n\n"
        "3 1 0 0 0 0 0 0 1 c.jpg\n\n"
        "4 1 0 0 0 0 0 0 1 d.jpg\n\n",
        encoding="utf-8",
    )
    return patch_dir


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


def test_requested_holdout_uses_registered_names_without_full_sparse_model(tmp_path: Path) -> None:
    selection = select_holdout(
        patch_dir=_minimal_patch(tmp_path),
        holdout_fraction=0.1,
        requested_holdout=["a.jpg", "c.jpg"],
    )

    assert selection.holdout_images == ["a.jpg", "c.jpg"]
    assert selection.train_images == ["b.jpg", "d.jpg"]


def test_patch_ids_are_selected_per_job(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = _job(tmp_path, variant="first")
    second = _job(tmp_path, variant="second")
    _patches(first, [f"p{index:03d}" for index in range(20)])
    _patches(second, [f"p{index:03d}" for index in range(2, 22)])

    assert _patch_ids_by_job(config=config, jobs=[first, second]) == {
        first.job_id: ["p000", "p002", "p004", "p006", "p008", "p011", "p013", "p015", "p017", "p019"],
        second.job_id: ["p002", "p004", "p006", "p008", "p010", "p013", "p015", "p017", "p019", "p021"],
    }


def test_patch_selection_does_not_write_holdouts(tmp_path: Path) -> None:
    config = _config(tmp_path, patch_count=5)
    first = _job(tmp_path, variant="first")
    _patches(first, [f"p{index:03d}" for index in range(5)])

    assert _patch_ids_by_job(config=config, jobs=[first]) == {
        first.job_id: ["p000", "p001", "p002", "p003", "p004"]
    }
    assert not (config.output_root / "holdouts").exists()


def test_patch_tasks_use_job_scoped_holdouts(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = _job(tmp_path, variant="first")
    _patches(first, ["p000"])

    task = _patch_tasks(config=config, job=first, patch_ids=["p000"])[0]

    assert task.holdout_path == config.output_root / "holdouts" / "dataset1" / first.job_id / "patch400" / "p000.json"


def test_next_attempt_dir_preserves_existing_attempts(tmp_path: Path) -> None:
    (tmp_path / "attempt_1").mkdir()
    (tmp_path / "attempt_2").mkdir()

    assert _next_attempt_dir(tmp_path) == tmp_path / "attempt_3"


def test_retryable_width_failure_requires_failed_status(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    log.write_text("CUDA driver version\nOUT_OF_MEMORY: Failed to allocate bucket buffers\n", encoding="utf-8")

    assert not _is_retryable_width_failure({"status": "warning"}, log)
    assert _is_retryable_width_failure({"status": "failed"}, log)
