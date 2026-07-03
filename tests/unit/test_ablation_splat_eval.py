"""Tests for ablation splat eval continuation helpers."""

from __future__ import annotations

from pathlib import Path

from reefs.experiments.ablations.config import AblationConfig, DatasetSpec, SfMVariant
from reefs.experiments.ablations.grid import SfMJob, SplatJob
from reefs.experiments.ablations.splat_eval import (
    _bounded_steps,
    _clean_sfm_jobs,
    _is_retryable_width_failure,
    _next_attempt_dir,
    _holdout_path,
    _patch_ids_by_job,
    _patch_tasks,
    _upsert_metrics_long,
)
from reefs.eval.holdout import _image_set_hash, build_eval_dataset, load_or_create_holdout, select_holdout
from reefs.experiments.ablations.ledger import SFM_FIELDS, atomic_write_csv


def _config(tmp_path: Path, *, patch_count: int = 10) -> AblationConfig:
    return AblationConfig(
        output_root=tmp_path / "ablations",
        datasets=[],
        sfm_variants=[],
        aims_baseline_overrides={},
        patch_sizes=[400],
        splat_counts=[1_000_000],
        max_widths=[4096],
        validation_patch_count=patch_count,
        holdout_fraction=0.1,
        sfm_timeout_hours=20,
        default_patch_size=400,
        default_splat_count=1_000_000,
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
        splat_count=1_000_000,
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


def _minimal_patch_with_names(tmp_path: Path, names: list[str]) -> Path:
    patch_dir = tmp_path / ("patch_" + str(len(names)) + "_" + names[0].replace(".", "_"))
    (patch_dir / "sparse" / "0").mkdir(parents=True)
    patch_dir.joinpath("patch_metadata.json").write_text(
        '{"patch_id":"p000","selected_images":'
        + str(names).replace("'", '"')
        + ',"selected_internal_count":'
        + str(len(names))
        + "}",
        encoding="utf-8",
    )
    lines = []
    for index, name in enumerate(names, start=1):
        lines.append(f"{index} 1 0 0 0 {index}.0 0 0 1 {name}\n\n")
    (patch_dir / "sparse" / "0" / "images.txt").write_text("".join(lines), encoding="utf-8")
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


def test_patch_selection_uses_available_patches_when_fewer_than_requested(tmp_path: Path) -> None:
    config = _config(tmp_path, patch_count=10)
    first = _job(tmp_path, variant="first")
    _patches(first, [f"p{index:03d}" for index in range(9)])

    assert _patch_ids_by_job(config=config, jobs=[first]) == {
        first.job_id: ["p000", "p001", "p002", "p003", "p004", "p005", "p006", "p007", "p008"]
    }


def test_patch_tasks_use_job_scoped_holdouts(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = _job(tmp_path, variant="first")
    _patches(first, ["p000"])

    task = _patch_tasks(config=config, job=first, patch_ids=["p000"])[0]

    assert task.holdout_path == config.output_root / "holdouts" / "dataset1" / first.job_id / "patch400" / "p000.json"


def test_stage2_holdout_path_is_shared_across_splat_counts(tmp_path: Path) -> None:
    config = _config(tmp_path)
    dataset = DatasetSpec(name="dataset1", config=tmp_path / "dataset.yml", project_dir=tmp_path / "dataset1")
    first = SplatJob(dataset=dataset, patch_size=400, splat_count=500_000, max_width=None, sfm_variant="best")
    second = SplatJob(dataset=dataset, patch_size=400, splat_count=1_000_000, max_width=None, sfm_variant="best")

    assert _holdout_path(config=config, job=first, patch_id="p000") == _holdout_path(
        config=config, job=second, patch_id="p000"
    )
    assert _holdout_path(config=config, job=first, patch_id="p000") == (
        config.output_root / "holdouts" / "dataset1" / "stage2" / "best" / "patch400" / "p000" / "holdout.json"
    )


def test_existing_holdout_manifest_is_not_rewritten(tmp_path: Path) -> None:
    patch = _minimal_patch_with_names(tmp_path, ["a.jpg", "b.jpg", "c.jpg", "d.jpg"])
    canonical = tmp_path / "holdout.json"
    canonical.write_text(
        '{\n'
        '  "patch_id": "p000",\n'
        '  "requested_holdout_images": ["a.jpg"],\n'
        f'  "image_set_hash": "{_image_set_hash(["a.jpg", "b.jpg", "c.jpg", "d.jpg"])}",\n'
        '  "custom_note": "keep me"\n'
        '}\n',
        encoding="utf-8",
    )

    selection = load_or_create_holdout(patch_dir=patch, canonical_path=canonical, holdout_fraction=0.1)

    assert selection.holdout_images == ["a.jpg"]
    assert "custom_note" in canonical.read_text(encoding="utf-8")


def test_existing_holdout_fails_when_patch_image_set_changes(tmp_path: Path) -> None:
    patch = _minimal_patch_with_names(tmp_path, ["a.jpg", "b.jpg", "renamed.jpg", "d.jpg"])
    canonical = tmp_path / "holdout.json"
    canonical.write_text(
        '{\n'
        '  "patch_id": "p000",\n'
        '  "requested_holdout_images": ["a.jpg"],\n'
        f'  "image_set_hash": "{_image_set_hash(["a.jpg", "b.jpg", "c.jpg", "d.jpg"])}"\n'
        '}\n',
        encoding="utf-8",
    )

    try:
        load_or_create_holdout(patch_dir=patch, canonical_path=canonical, holdout_fraction=0.1)
    except ValueError as exc:
        assert "image set does not match" in str(exc)
    else:
        raise AssertionError("expected holdout image set mismatch to fail")


def test_build_eval_dataset_writes_target_source_manifest(tmp_path: Path) -> None:
    patch = _minimal_patch_with_names(tmp_path, ["a.jpg", "b.jpg", "c.jpg", "d.jpg"])
    (patch / "selected_images").mkdir()
    for name in ["a.jpg", "b.jpg", "c.jpg", "d.jpg"]:
        (patch / "selected_images" / name).write_text("fake", encoding="utf-8")
    (patch / "sparse" / "0" / "cameras.txt").write_text("# cameras\n", encoding="utf-8")
    (patch / "sparse" / "0" / "points3D.txt").write_text("# points\n", encoding="utf-8")
    holdout = load_or_create_holdout(patch_dir=patch, canonical_path=tmp_path / "holdout.json", holdout_fraction=0.1)

    build_eval_dataset(
        patch_dir=patch,
        output_dir=tmp_path / "eval_dataset",
        holdout=holdout,
        target_image_source="resized_undistorted",
    )

    manifest = (tmp_path / "eval_dataset" / "eval_dataset_manifest.json").read_text(encoding="utf-8")
    assert '"target_image_source": "resized_undistorted"' in manifest
    assert '"uses_patch_training_images": true' in manifest
    assert '"is_full_resolution_eval": false' in manifest


def test_next_attempt_dir_preserves_existing_attempts(tmp_path: Path) -> None:
    (tmp_path / "attempt_1").mkdir()
    (tmp_path / "attempt_2").mkdir()

    assert _next_attempt_dir(tmp_path) == tmp_path / "attempt_3"


def test_bounded_steps_keeps_final_iteration() -> None:
    assert _bounded_steps([5000, 10000, 15000], 12000) == [5000, 10000, 12000]
    assert _bounded_steps([5000, 10000, 15000], 15000) == [5000, 10000, 15000]


def test_metrics_long_upsert_replaces_same_attempt_rows(tmp_path: Path) -> None:
    config = _config(tmp_path)
    job = _job(tmp_path, variant="first")
    _patches(job, ["p000"])
    task = _patch_tasks(config=config, job=job, patch_ids=["p000"])[0]
    attempt_dir = task.output_dir / "attempt_1"
    metrics_path = attempt_dir / "metrics.csv"
    metrics_path.parent.mkdir(parents=True)

    _upsert_metrics_long(
        path=config.output_root / "metrics_long.csv",
        task=task,
        attempt_dir=attempt_dir,
        metrics_path=metrics_path,
        rows=[
            {"iteration": 5000, "psnr": 20.0, "ssim": 0.6, "time_per_image": 0.1, "num_gaussians": 100},
            {"iteration": 10000, "psnr": 21.0, "ssim": 0.7, "lpips": 0.3, "time_per_image": 0.1, "num_gaussians": 120},
        ],
        max_width=2048,
    )
    _upsert_metrics_long(
        path=config.output_root / "metrics_long.csv",
        task=task,
        attempt_dir=attempt_dir,
        metrics_path=metrics_path,
        rows=[
            {"iteration": 5000, "psnr": 22.0, "ssim": 0.8, "time_per_image": 0.2, "num_gaussians": 130},
        ],
        max_width=2048,
    )

    rows = (config.output_root / "metrics_long.csv").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 2
    assert "22.0" in rows[1]
    assert "20.0" not in rows[1]


def test_retryable_width_failure_requires_failed_status(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    log.write_text("CUDA driver version\nOUT_OF_MEMORY: Failed to allocate bucket buffers\n", encoding="utf-8")

    assert not _is_retryable_width_failure({"status": "warning"}, log)
    assert _is_retryable_width_failure({"status": "failed"}, log)
