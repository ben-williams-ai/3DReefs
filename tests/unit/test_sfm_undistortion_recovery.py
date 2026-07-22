"""Tests for the SfM pipeline's one-shot undistortion recovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from reefs.colmap.runner import IMAGE_METADATA_WRITE_FAILURE, ColmapCommandError, CommandResult
from reefs.config.loader import load_config
from reefs.logging.timings import TimingRecorder
from reefs.sfm import pipeline
from reefs.sfm.metadata_recovery import MetadataRecoveryResult
from reefs.sfm.validation import SfMPaths


def _config(tmp_path: Path):
    path = tmp_path / "config.yml"
    path.write_text(
        f"""
colour_restoration:
  mode: off
  overwrite: false
  start_sfm_immediately: true
project:
  dir: {tmp_path}
tools:
  colmap_bin: colmap
  lfs_bin: LichtFeld-Studio
  splat_transform_bin: splat-transform
""".lstrip(),
        encoding="utf-8",
    )
    return load_config(path)


def _paths(tmp_path: Path) -> SfMPaths:
    root = tmp_path / "sfm"
    root.mkdir(exist_ok=True)
    return SfMPaths(
        root=root,
        database=root / "database.db",
        sparse=root / "sparse",
        selected_sparse=root / "selected_sparse",
        selected_sparse_text=root / "selected_sparse_txt",
        refined_sparse=root / "refined_sparse",
        cross_camera_pairs=root / "cross_camera_pairs",
        undistorted=root / "undistorted",
        full_resolution_undistorted=root / "undistorted_full_resolution",
        dense=root / "dense",
        colmap_log=root / "colmap.log",
    )


def _completed(command) -> CommandResult:
    return CommandResult(command.stage, command.args, 0, "start", "end", 1.0)


def _recovery(source: Path, recovered: Path, audit: Path) -> MetadataRecoveryResult:
    recovered.mkdir(parents=True)
    return MetadataRecoveryResult(
        source_root=str(source),
        recovered_root=str(recovered),
        image_count=2,
        staging_method="hardlink",
        exiftool_version="13.40",
        source_hash_manifest=str(audit / "before.sha256"),
        recovered_hash_manifest=str(audit / "after.sha256"),
    )


def _invoke(
    *,
    tmp_path: Path,
    monkeypatch,
    run,
    state: pipeline._UndistortionRecoveryState | None = None,
    output_name: str = "undistorted",
):
    paths = _paths(tmp_path) if state is None else _paths_for_state(tmp_path)
    source = tmp_path / "raw"
    source.mkdir(exist_ok=True)
    state = state or pipeline._UndistortionRecoveryState(source)
    result = pipeline.SfMRunResult(paths=paths)
    monkeypatch.setattr(pipeline, "_run", run)
    command_result = pipeline._run_undistortion_pass(
        config=_config(tmp_path),
        recovery_state=state,
        input_path=tmp_path / "sparse",
        output_path=paths.root / output_name,
        paths=paths,
        timings=TimingRecorder(),
        result=result,
        recorder=None,
    )
    return command_result, state, result, paths


def _paths_for_state(tmp_path: Path) -> SfMPaths:
    root = tmp_path / "sfm"
    return SfMPaths(
        root=root,
        database=root / "database.db",
        sparse=root / "sparse",
        selected_sparse=root / "selected_sparse",
        selected_sparse_text=root / "selected_sparse_txt",
        refined_sparse=root / "refined_sparse",
        cross_camera_pairs=root / "cross_camera_pairs",
        undistorted=root / "undistorted",
        full_resolution_undistorted=root / "undistorted_full_resolution",
        dense=root / "dense",
        colmap_log=root / "colmap.log",
    )


def test_successful_undistortion_does_not_prepare_metadata_recovery(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "prepare_metadata_stripped_images",
        lambda **kwargs: pytest.fail("metadata recovery should not run"),
    )

    completed, state, result, _ = _invoke(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        run=lambda command, **kwargs: _completed(command),
    )

    assert completed.returncode == 0
    assert state.recovery is None
    assert result.warnings == []


def test_recognised_failure_recovers_once_and_removes_only_failed_output(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[Path] = []
    output = tmp_path / "sfm" / "undistorted"
    output.mkdir(parents=True)
    (output / "partial.jpg").write_bytes(b"")
    preserved = tmp_path / "sfm" / "already_complete"
    preserved.mkdir()
    (preserved / "keep.jpg").write_bytes(b"keep")

    def run(command, **kwargs):
        image_root = Path(command.args[command.args.index("--image_path") + 1])
        calls.append(image_root)
        if len(calls) == 1:
            raise ColmapCommandError("failed", failure_kind=IMAGE_METADATA_WRITE_FAILURE)
        assert not output.exists()
        return _completed(command)

    recoveries = 0

    def recover(*, source_root, recovered_root, audit_root):
        nonlocal recoveries
        recoveries += 1
        return _recovery(source_root, recovered_root, audit_root)

    monkeypatch.setattr(pipeline, "prepare_metadata_stripped_images", recover)
    completed, state, result, paths = _invoke(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        run=run,
    )

    assert completed.returncode == 0
    assert recoveries == 1
    assert calls == [tmp_path / "raw", paths.root / "metadata_stripped_raw"]
    assert (preserved / "keep.jpg").read_bytes() == b"keep"
    assert len(result.warnings) == 1
    record = json.loads((paths.root / "undistortion_metadata_recovery.json").read_text())
    assert record["status"] == "complete"
    assert record["retry_returncode"] == 0


def test_unrelated_failure_propagates_without_recovery(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "prepare_metadata_stripped_images",
        lambda **kwargs: pytest.fail("metadata recovery should not run"),
    )

    with pytest.raises(ColmapCommandError) as captured:
        _invoke(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            run=lambda command, **kwargs: (_ for _ in ()).throw(ColmapCommandError("generic")),
        )

    assert captured.value.failure_kind is None


def test_retry_failure_is_recorded_and_never_retried_again(tmp_path: Path, monkeypatch) -> None:
    calls = 0

    def run(command, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ColmapCommandError("metadata", failure_kind=IMAGE_METADATA_WRITE_FAILURE)
        raise ColmapCommandError("retry failed", failure_kind=IMAGE_METADATA_WRITE_FAILURE)

    monkeypatch.setattr(
        pipeline,
        "prepare_metadata_stripped_images",
        lambda source_root, recovered_root, audit_root: _recovery(
            source_root, recovered_root, audit_root
        ),
    )

    with pytest.raises(ColmapCommandError, match="retry failed"):
        _invoke(tmp_path=tmp_path, monkeypatch=monkeypatch, run=run)

    assert calls == 2
    record = json.loads(
        (tmp_path / "sfm" / "undistortion_metadata_recovery.json").read_text()
    )
    assert record["status"] == "retry_failed"


def test_later_pass_reuses_existing_verified_recovery(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "raw"
    source.mkdir()
    recovered = tmp_path / "sfm" / "metadata_stripped_raw"
    recovered.parent.mkdir()
    state = pipeline._UndistortionRecoveryState(
        image_root=recovered,
        recovery=_recovery(source, recovered, tmp_path / "sfm" / "audit"),
        attempted=True,
    )
    seen: list[Path] = []

    def run(command, **kwargs):
        seen.append(Path(command.args[command.args.index("--image_path") + 1]))
        return _completed(command)

    completed, _, _, _ = _invoke(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        run=run,
        state=state,
        output_name="undistorted_2048",
    )

    assert completed.returncode == 0
    assert seen == [recovered]


def test_three_pass_sequence_recovers_once_then_reuses_sanitised_root(
    tmp_path: Path, monkeypatch
) -> None:
    paths = _paths(tmp_path)
    source = tmp_path / "raw"
    source.mkdir()
    state = pipeline._UndistortionRecoveryState(source)
    result = pipeline.SfMRunResult(paths=paths)
    seen: list[Path] = []

    def run(command, **kwargs):
        seen.append(Path(command.args[command.args.index("--image_path") + 1]))
        if len(seen) == 1:
            raise ColmapCommandError("metadata", failure_kind=IMAGE_METADATA_WRITE_FAILURE)
        return _completed(command)

    recoveries = 0

    def recover(*, source_root, recovered_root, audit_root):
        nonlocal recoveries
        recoveries += 1
        return _recovery(source_root, recovered_root, audit_root)

    monkeypatch.setattr(pipeline, "_run", run)
    monkeypatch.setattr(pipeline, "prepare_metadata_stripped_images", recover)
    for output, size, full in [
        (paths.undistorted, None, False),
        (paths.root / "undistorted_2048", 2048, False),
        (paths.full_resolution_undistorted, None, True),
    ]:
        pipeline._run_undistortion_pass(
            config=_config(tmp_path),
            recovery_state=state,
            input_path=tmp_path / "sparse",
            output_path=output,
            paths=paths,
            timings=TimingRecorder(),
            result=result,
            recorder=None,
            max_image_size=size,
            full_resolution=full,
        )

    recovered = paths.root / "metadata_stripped_raw"
    assert recoveries == 1
    assert seen == [source, recovered, recovered, recovered]
    assert state.attempted is True


def test_finalize_recovery_removes_only_temporary_tree_and_updates_audit(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    source = tmp_path / "raw"
    source.mkdir()
    recovered = paths.root / "metadata_stripped_raw"
    recovery = _recovery(source, recovered, paths.root / "audit")
    preserved = paths.root / "undistorted"
    preserved.mkdir()
    (preserved / "keep.jpg").write_bytes(b"keep")
    record = paths.root / "undistortion_metadata_recovery.json"
    record.write_text('{"status": "complete"}\n', encoding="utf-8")

    pipeline._finalize_undistortion_metadata_recovery(
        recovery_state=pipeline._UndistortionRecoveryState(
            image_root=recovered,
            recovery=recovery,
            attempted=True,
        ),
        paths=paths,
    )

    assert not recovered.exists()
    assert (preserved / "keep.jpg").read_bytes() == b"keep"
    assert json.loads(record.read_text())["temporary_tree_removed"] is True
