"""Tests for post-processing cleanup helpers."""

from __future__ import annotations

import sys
import types
from pathlib import Path

from reefs.config.models import SplatCleanupConfig
from reefs.postprocess.artifacts import PatchTrainingSource
from reefs.postprocess import cleanup as cleanup_module
from reefs.postprocess.cleanup import clean_patch_source, validate_cleanup_backend


def _write_ply(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ply\nformat ascii 1.0\nelement vertex 1\nend_header\n", encoding="utf-8")
    return path


def _source(path: Path) -> PatchTrainingSource:
    ply = _write_ply(path / "p000" / "splat" / "splat_finished.ply")
    return PatchTrainingSource(
        patch_id="p000",
        patch_dir=path / "p000",
        source_file=ply,
        source_kind="finished",
        requested_iterations=100,
        completed_iterations=100,
        completion_ratio=1.0,
        severity="normal",
        usable=True,
        reason="completed_training_output",
    )


def _install_fake_wildflow(monkeypatch, cleanup_calls: list[dict[str, object]] | None = None) -> None:
    wildflow = types.ModuleType("wildflow")
    splat = types.ModuleType("wildflow.splat")

    def cleanup_splats(params: dict[str, object]) -> None:
        if cleanup_calls is not None:
            cleanup_calls.append(params)
        Path(str(params["output_file"])).write_text(Path(str(params["input_file"])).read_text(encoding="utf-8"), encoding="utf-8")

    splat.cleanup_splats = cleanup_splats
    splat.merge_ply_files = lambda _params: None
    wildflow.splat = splat
    monkeypatch.setitem(sys.modules, "wildflow", wildflow)
    monkeypatch.setitem(sys.modules, "wildflow.splat", splat)


def test_validate_cleanup_backend_fails_missing_wildflow(monkeypatch) -> None:
    def fail_import(name: str):
        raise ImportError(name)

    monkeypatch.setattr(cleanup_module.importlib, "import_module", fail_import)

    result = validate_cleanup_backend(SplatCleanupConfig())

    assert result.status == "failed"
    assert "wildflow" in result.message


def test_validate_cleanup_backend_requires_cleanup_and_merge_callables(monkeypatch) -> None:
    _install_fake_wildflow(monkeypatch)

    result = validate_cleanup_backend(SplatCleanupConfig())

    assert result.status == "passed"


def test_clean_patch_source_uses_wildflow_params(tmp_path: Path, monkeypatch) -> None:
    cleanup_calls: list[dict[str, object]] = []
    _install_fake_wildflow(monkeypatch, cleanup_calls)
    patch_dir = tmp_path / "p000"
    patch_dir.mkdir(parents=True)
    (patch_dir / "patch_metadata.json").write_text(
        (
            '{"bounds": {"min_x": 0, "max_x": 10, "min_y": 1, '
            '"max_y": 11, "min_z": -2, "max_z": 3, "buffer": 0.1}}'
        ),
        encoding="utf-8",
    )

    record = clean_patch_source(
        source=_source(tmp_path),
        config=SplatCleanupConfig(),
    )

    assert record.status == "complete"
    assert record.output_file is not None
    assert record.output_file.name == "splat_finished_clean.ply"
    assert record.before_splat_count == 1
    assert record.after_splat_count == 1
    assert cleanup_calls[0]["max_area"] == 0.004
    assert cleanup_calls[0]["min_neighbors"] == 20
    assert cleanup_calls[0]["radius"] == 0.05
    assert cleanup_calls[0]["min_x"] == 0.1
    assert cleanup_calls[0]["max_x"] == 9.9


def test_clean_patch_source_rejects_old_top_level_bounds_metadata(tmp_path: Path, monkeypatch) -> None:
    cleanup_calls: list[dict[str, object]] = []
    _install_fake_wildflow(monkeypatch, cleanup_calls)
    patch_dir = tmp_path / "p000"
    patch_dir.mkdir(parents=True)
    (patch_dir / "patch_metadata.json").write_text(
        '{"min_x": -2, "max_x": 8, "min_y": 1, "max_y": 11, "min_z": -2, "max_z": 3}',
        encoding="utf-8",
    )

    record = clean_patch_source(
        source=_source(tmp_path),
        config=SplatCleanupConfig(),
    )

    assert record.status == "failed"
    assert cleanup_calls == []
    assert "canonical nested bounds" in record.warnings[0]


def test_clean_patch_source_skips_unusable_source(tmp_path: Path) -> None:
    source = PatchTrainingSource(
        patch_id="p000",
        patch_dir=tmp_path / "p000",
        source_file=None,
        source_kind="iteration",
        requested_iterations=None,
        completed_iterations=None,
        completion_ratio=None,
        severity="failed",
        usable=False,
        reason="no_usable_ply",
    )

    record = clean_patch_source(
        source=source,
        config=SplatCleanupConfig(),
    )

    assert record.status == "skipped"
    assert record.warnings == ["no_usable_ply"]
