"""Tests for ablation runner smoke output."""

from __future__ import annotations

from pathlib import Path

from reefs.experiments.ablations.config import AblationConfig, DatasetSpec, SfMVariant
from reefs.experiments.ablations.grid import SfMJob
from reefs.experiments.ablations.ledger import SPLAT_FIELDS, read_rows
from reefs.experiments.ablations.runner import (
    _append_job_event,
    _append_job_warning,
    _command_attempt_dir,
    _latest_log_path,
    _sfm_quality_warning,
    _stage_completed,
    _write_effective_config_snapshot,
    _write_job_identity,
    dry_run,
    run_splat_grid_job,
    smoke,
    write_stage2_manifest,
)


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
        splat_counts=[1_000_000],
        max_widths=[4096],
        validation_patch_count=5,
        holdout_fraction=0.1,
        validation_target_image_source="training_undistorted",
        validation_full_resolution_undistorted_images_dir=None,
        validation_allow_full_resolution_target=False,
        sfm_timeout_hours=20,
        default_patch_size=400,
        default_splat_count=1_000_000,
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
        splat_counts=[1_000_000],
        max_widths=[],
        validation_patch_count=2,
        holdout_fraction=0.1,
        validation_target_image_source="training_undistorted",
        validation_full_resolution_undistorted_images_dir=None,
        validation_allow_full_resolution_target=False,
        sfm_timeout_hours=20,
        default_patch_size=400,
        default_splat_count=1_000_000,
        run_validation_splats_for_sfm=True,
    )

    run_splat_grid_job(
        config=config,
        job_id="splat_dataset1_best_patch400_1m",
        source_sfm_variant="sfm_baseline",
        simulate=True,
        force_jobs=set(),
    )

    rows = read_rows(config.output_root / "results_splat.csv")
    assert list(rows[0]) == SPLAT_FIELDS
    assert rows[0]["job_id"] == "splat_eval_splat_dataset1_best_patch400_1m_p000"
    assert rows[0]["patch_size"] == "400"
    assert rows[0]["splat_count"] == "1000000"


def test_stage2_simulation_accepts_selected_sfm_variant_job_id(tmp_path: Path) -> None:
    config = AblationConfig(
        output_root=tmp_path / "ablations",
        datasets=[
            DatasetSpec(
                name="dataset1",
                config=Path("configs/datasets/dataset_01.yml"),
                project_dir=tmp_path / "dataset1",
            )
        ],
        sfm_variants=[SfMVariant(name="sfm_full_sift_global", description="baseline")],
        aims_baseline_overrides={},
        patch_sizes=[400],
        splat_counts=[1_000_000],
        max_widths=[],
        validation_patch_count=2,
        holdout_fraction=0.1,
        validation_target_image_source="training_undistorted",
        validation_full_resolution_undistorted_images_dir=None,
        validation_allow_full_resolution_target=False,
        sfm_timeout_hours=20,
        default_patch_size=400,
        default_splat_count=1_000_000,
        run_validation_splats_for_sfm=True,
    )

    run_splat_grid_job(
        config=config,
        job_id="splat_dataset1_sfm_full_sift_global_patch400_1m",
        source_sfm_variant="sfm_full_sift_global",
        simulate=True,
        force_jobs=set(),
    )

    rows = read_rows(config.output_root / "results_splat.csv")
    assert rows[0]["variant"] == "sfm_full_sift_global"


def test_stage2_manifest_writes_selected_source_manifest(tmp_path: Path) -> None:
    config = AblationConfig(
        output_root=tmp_path / "ablations",
        datasets=[
            DatasetSpec(
                name="dataset1",
                config=Path("configs/datasets/dataset_01.yml"),
                project_dir=tmp_path / "dataset1",
            )
        ],
        sfm_variants=[SfMVariant(name="sfm_full_sift_global", description="baseline")],
        aims_baseline_overrides={},
        patch_sizes=[200, 400],
        splat_counts=[500_000, 1_000_000],
        max_widths=[],
        validation_patch_count=2,
        holdout_fraction=0.1,
        validation_target_image_source="training_undistorted",
        validation_full_resolution_undistorted_images_dir=None,
        validation_allow_full_resolution_target=False,
        sfm_timeout_hours=20,
        default_patch_size=400,
        default_splat_count=1_000_000,
        run_validation_splats_for_sfm=True,
    )

    write_stage2_manifest(config=config, sfm_variant="sfm_full_sift_global")

    manifest = (config.output_root / "manifest_stage2_sfm_full_sift_global.csv").read_text(encoding="utf-8")
    source = (config.output_root / "stage2_source_sfm_full_sift_global.json").read_text(encoding="utf-8")
    assert "splat_dataset1_sfm_full_sift_global_patch200_500k" in manifest
    assert '"source_sfm_variant": "sfm_full_sift_global"' in source
    assert '"job_count": 4' in source


def test_dry_run_writes_review_summary(tmp_path: Path, capsys) -> None:
    config = AblationConfig(
        output_root=tmp_path / "ablations",
        datasets=[
            DatasetSpec(
                name="dataset1",
                config=Path("configs/datasets/dataset_01.yml"),
                project_dir=tmp_path / "dataset1",
            )
        ],
        sfm_variants=[
            SfMVariant(name="sfm_baseline", description="baseline"),
            SfMVariant(name="sfm_incremental", description="incremental"),
        ],
        aims_baseline_overrides={},
        patch_sizes=[200, 400],
        splat_counts=[1_000_000],
        max_widths=[4096],
        validation_patch_count=2,
        holdout_fraction=0.1,
        validation_target_image_source="training_undistorted",
        validation_full_resolution_undistorted_images_dir=None,
        validation_allow_full_resolution_target=False,
        sfm_timeout_hours=20,
        default_patch_size=400,
        default_splat_count=1_000_000,
        run_validation_splats_for_sfm=True,
    )

    dry_run(config)

    summary = (config.output_root / "dry_run_summary.json").read_text(encoding="utf-8")
    printed = capsys.readouterr().out
    assert '"sfm_stage1": 2' in summary
    assert '"splat_stage2": 2' in summary
    assert '"sfm_upper_bound": 40' in summary
    assert str(config.output_root / "jobs") in printed


def test_stage_completed_requires_matching_run_status(tmp_path: Path) -> None:
    status = tmp_path / "run_status.json"

    assert not _stage_completed(status, "splat.patch")
    status.write_text('{"stage_statuses":{"splat.preflight":"complete"}}', encoding="utf-8")
    assert not _stage_completed(status, "splat.patch")
    status.write_text('{"stage_statuses":{"splat.patch":"complete"}}', encoding="utf-8")
    assert _stage_completed(status, "splat.patch")


def test_sfm_quality_warning_catches_fragmented_and_empty_models() -> None:
    warning = _sfm_quality_warning(
        {
            "registered_images_percent": 72.0,
            "sparse_model_count": 2,
            "connected_components": 3,
            "largest_component_percent": 61.5,
            "mean_reprojection_error_px": 0.0,
            "median_reprojection_error_px": 0.0,
            "sparse_point_count": 0,
            "cross_camera_verified_pairs": 0,
        },
        backend="global",
    )

    assert "multiple_sparse_models:2" in warning
    assert "global_registered_below_90_percent:72.00" in warning
    assert "largest_component_below_80_percent:61.50" in warning
    assert "fragmented_graph_components:3" in warning
    assert "zero_sparse_points" in warning
    assert "zero_mean_reprojection_error" in warning


def test_sfm_quality_warning_uses_incremental_registration_threshold() -> None:
    warning = _sfm_quality_warning(
        {
            "registered_images_percent": 85.0,
            "sparse_model_count": 1,
            "connected_components": 1,
            "largest_component_percent": 100.0,
            "mean_reprojection_error_px": 0.5,
            "median_reprojection_error_px": 0.4,
            "sparse_point_count": 10_000,
            "cross_camera_verified_pairs": 10,
        },
        backend="incremental",
    )

    assert warning == ""


def test_job_identity_and_events_are_written_before_launch(tmp_path: Path) -> None:
    dataset = DatasetSpec(name="dataset1", config=tmp_path / "dataset.yml", project_dir=tmp_path / "dataset1")
    job = SfMJob(
        dataset=dataset,
        variant=SfMVariant(name="baseline", description="baseline"),
        patch_size=400,
        splat_count=1_000_000,
    )
    job_dir = tmp_path / "jobs" / job.job_id

    _write_job_identity(
        job_dir=job_dir,
        job=job,
        steps="sfm",
        command=["python", "main.py"],
        overrides={"advanced.sfm.reconstruction.backend": "global"},
        resume_policy="overwrite",
        timeout_seconds=10,
    )
    _append_job_event(job_dir, "running", {"steps": "sfm"})

    assert (job_dir / "run_identity.json").exists()
    assert (job_dir / "command_record.json").exists()
    assert '"run_id": "sfm_dataset1_baseline"' in (job_dir / "run_identity.json").read_text(encoding="utf-8")
    assert '"timeout_seconds": 10' in (job_dir / "command_record.json").read_text(encoding="utf-8")
    assert '"state": "running"' in (job_dir / "events.jsonl").read_text(encoding="utf-8")


def test_job_events_reject_unknown_states(tmp_path: Path) -> None:
    try:
        _append_job_event(tmp_path, "done", {})
    except ValueError as exc:
        assert "unknown ablation event state: done" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_job_warnings_are_written_as_jsonl(tmp_path: Path) -> None:
    _append_job_warning(tmp_path, "low_registration;zero_sparse_points", {"phase": "sfm"})

    warnings = (tmp_path / "warnings.jsonl").read_text(encoding="utf-8")
    assert '"warning": "low_registration"' in warnings
    assert '"warning": "zero_sparse_points"' in warnings
    assert '"phase": "sfm"' in warnings


def test_repeated_commands_use_timestamped_attempt_dirs(tmp_path: Path) -> None:
    job_dir = tmp_path / "jobs" / "sfm_dataset1_baseline"
    job_dir.mkdir(parents=True)

    first = _command_attempt_dir(job_dir, "sfm_command.log")
    assert first == job_dir

    (job_dir / "sfm_command.log").write_text("old", encoding="utf-8")
    retry = _command_attempt_dir(job_dir, "sfm_command.log")

    assert retry.parent == job_dir / "attempts"
    assert retry.name


def test_latest_log_path_follows_attempt_pointer(tmp_path: Path) -> None:
    job_dir = tmp_path / "jobs" / "sfm_dataset1_baseline"
    attempt_dir = job_dir / "attempts" / "20260703T000000Z"
    attempt_dir.mkdir(parents=True)
    log_path = attempt_dir / "sfm_command.log"
    log_path.write_text("new", encoding="utf-8")
    (job_dir / "latest_attempt.json").write_text(
        '{"log_path": "' + str(log_path) + '"}',
        encoding="utf-8",
    )

    assert _latest_log_path(job_dir, "sfm_command.log") == log_path


def test_effective_config_snapshot_records_ablation_overrides(tmp_path: Path) -> None:
    dataset = DatasetSpec(name="dataset1", config=Path("configs/example.yml"), project_dir=tmp_path / "dataset1")
    job = SfMJob(
        dataset=dataset,
        variant=SfMVariant(name="baseline", description="baseline"),
        patch_size=400,
        splat_count=1_000_000,
    )
    job_dir = tmp_path / "jobs" / job.job_id

    _write_effective_config_snapshot(
        job=job,
        job_dir=job_dir,
        overrides={
            "advanced.sfm.reconstruction.backend": "incremental",
            "advanced.sfm.feature_extraction.max_image_size": 2048,
        },
    )

    effective = (job_dir / "effective_config.yml").read_text(encoding="utf-8")
    overrides = (job_dir / "effective_config_overrides.json").read_text(encoding="utf-8")
    assert "dir: " + str(tmp_path / "dataset1") in effective
    assert "backend: incremental" in effective
    assert "max_image_size: 2048" in effective
    assert '"key": "advanced.sfm.reconstruction.backend"' in overrides
