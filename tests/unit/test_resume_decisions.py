"""Tests for resume decision helpers."""

from __future__ import annotations

from pathlib import Path

from reefs.io.yaml_json import write_json, write_yaml
from reefs.runs.resume import (
    build_config_diff_event,
    build_resume_event,
    diff_effective_configs,
    discover_partial_runs,
)


def _make_run(run_dir: Path, status: str = "preflight_failed") -> None:
    run_dir.mkdir(parents=True)
    write_json(
        run_dir / "run_status.json",
        {"status": status, "last_completed_stage": "sfm"},
    )
    write_json(run_dir / "run_manifest.json", {"requested_steps": ["sfm", "splat"]})
    write_yaml(
        run_dir / "effective_config.yml",
        {"advanced": {"splat": {"train": {"num_iters": 30000}}}},
    )


def test_discover_partial_run_for_requested_step(tmp_path: Path) -> None:
    _make_run(tmp_path / "run1")

    partials = discover_partial_runs(tmp_path, ["sfm"])

    assert len(partials) == 1
    assert partials[0].step == "sfm"


def test_missing_status_is_uncertain_partial(tmp_path: Path) -> None:
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    write_json(run_dir / "run_manifest.json", {"requested_steps": ["sfm"]})

    partials = discover_partial_runs(tmp_path, ["sfm"])

    assert partials[0].reason == "missing_or_corrupt_status"


def test_missing_records_with_sfm_outputs_are_detected_for_specific_sfm_step(tmp_path: Path) -> None:
    run_dir = tmp_path / "run1"
    sparse_text = run_dir / "sfm" / "selected_sparse_txt"
    sparse_text.mkdir(parents=True)
    (sparse_text / "cameras.txt").write_text("1 OPENCV 64 48 1 1 1 1 0 0 0 0\n", encoding="utf-8")
    (sparse_text / "images.txt").write_text("1 1 0 0 0 0 0 0 1 image_0001.jpg\n\n", encoding="utf-8")
    (sparse_text / "points3D.txt").write_text("1 0 0 0 255 255 255 1 1 0\n", encoding="utf-8")

    partials = discover_partial_runs(tmp_path, ["sfm.undistort"])

    assert len(partials) == 1
    assert partials[0].step == "sfm.undistort"
    assert partials[0].reason == "filesystem_outputs_without_status"


def test_complete_run_is_not_partial(tmp_path: Path) -> None:
    _make_run(tmp_path / "run1", status="complete")

    assert discover_partial_runs(tmp_path, ["sfm"]) == []


def test_effective_config_diff() -> None:
    differences = diff_effective_configs(
        {"advanced": {"splat": {"train": {"num_iters": 30000}}}},
        {"advanced": {"splat": {"train": {"num_iters": 20000}}}},
    )

    assert differences == [
        {
            "path": "advanced.splat.train.num_iters",
            "previous_value": 30000,
            "requested_value": 20000,
            "source": "effective_config",
        }
    ]


def test_resume_and_diff_events(tmp_path: Path) -> None:
    _make_run(tmp_path / "run1")
    partial = discover_partial_runs(tmp_path, ["sfm"])[0]

    resume_event = build_resume_event(
        partial=partial, decision="continue", source="resume_policy"
    )
    diff_event = build_config_diff_event(
        partial=partial,
        requested_config={"advanced": {"splat": {"train": {"num_iters": 20000}}}},
        decision="continue",
        interactive=False,
    )

    assert resume_event["decision"] == "continue"
    assert diff_event is not None
    assert diff_event["decision"] == "continue"
