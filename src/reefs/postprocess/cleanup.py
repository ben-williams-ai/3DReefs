"""Patch splat cleanup using wildflow."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from reefs.config.models import SplatCleanupConfig
from reefs.postprocess.artifacts import CleanupRecord, PatchTrainingSource, cleaned_output_for, ply_vertex_count


@dataclass(frozen=True)
class CleanupToolValidation:
    """Wildflow cleanup and merge validation result."""

    status: str
    backend: str
    message: str

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable validation result."""
        return {"status": self.status, "backend": self.backend, "message": self.message}


def validate_cleanup_backend(config: SplatCleanupConfig) -> CleanupToolValidation:
    """Validate required wildflow callables without doing heavy work."""
    if not config.enabled:
        return CleanupToolValidation("passed", "wildflow", "Cleanup disabled")
    try:
        module = importlib.import_module("wildflow.splat")
    except ImportError:
        return CleanupToolValidation("failed", "wildflow", "wildflow is not installed")
    missing = [
        name
        for name in ["cleanup_splats", "merge_ply_files"]
        if not callable(getattr(module, name, None))
    ]
    if missing:
        return CleanupToolValidation(
            "failed",
            "wildflow",
            "wildflow.splat is missing required callables: " + ", ".join(missing),
        )
    return CleanupToolValidation("passed", "wildflow", "wildflow cleanup and merge callables are available")


def cleanup_settings(config: SplatCleanupConfig) -> dict[str, object]:
    """Return serialisable cleanup settings."""
    return {
        "backend": "wildflow",
        "max_area": config.max_area,
        "min_neighbors": config.min_neighbors,
        "radius": config.radius,
        "filter_boundaries": config.filter_boundaries,
        "boundary_buffer": config.boundary_buffer,
    }


def _patch_boundaries(source: PatchTrainingSource, buffer: float) -> dict[str, float]:
    """Return wildflow boundary settings when patch metadata has bounds."""
    metadata = source.patch_dir / "patch_metadata.json"
    if not metadata.exists():
        return {}
    try:
        import json

        data = json.loads(metadata.read_text(encoding="utf-8"))
        boundaries = {
            "min_x": float(data["min_x"]) + buffer,
            "max_x": float(data["max_x"]) - buffer,
            "min_y": float(data["min_y"]) + buffer,
            "max_y": float(data["max_y"]) - buffer,
            "min_z": float(data["min_z"]),
            "max_z": float(data["max_z"]),
        }
    except (KeyError, TypeError, ValueError, OSError):
        return {}
    if boundaries["min_x"] >= boundaries["max_x"] or boundaries["min_y"] >= boundaries["max_y"]:
        return {}
    if boundaries["min_z"] >= boundaries["max_z"]:
        return {}
    return boundaries


def _wildflow_cleanup_params(
    source: PatchTrainingSource,
    output_file: Path,
    config: SplatCleanupConfig,
) -> dict[str, object]:
    assert source.source_file is not None
    params: dict[str, object] = {
        "input_file": str(source.source_file),
        "output_file": str(output_file),
        "max_area": config.max_area,
        "min_neighbors": config.min_neighbors,
        "radius": config.radius,
    }
    if config.filter_boundaries:
        params.update(_patch_boundaries(source, config.boundary_buffer))
    return params


def _run_wildflow_cleanup(params: dict[str, object]) -> None:
    module = importlib.import_module("wildflow.splat")
    module.cleanup_splats(params)


def clean_patch_source(
    *,
    source: PatchTrainingSource,
    config: SplatCleanupConfig,
) -> CleanupRecord:
    """Clean one patch source and return its status."""
    settings = cleanup_settings(config)
    before = ply_vertex_count(source.source_file) if source.source_file else None
    warnings: list[str] = []
    if not source.usable or source.source_file is None:
        return CleanupRecord(
            patch_id=source.patch_id,
            source=source,
            output_file=None,
            status="skipped",
            cleanup_settings=settings,
            before_splat_count=before,
            after_splat_count=None,
            warnings=[source.reason],
        )
    output_file = cleaned_output_for(source.source_file)
    start = perf_counter()
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        _run_wildflow_cleanup(_wildflow_cleanup_params(source, output_file, config))
        after = ply_vertex_count(output_file)
        return CleanupRecord(
            patch_id=source.patch_id,
            source=source,
            output_file=output_file,
            status="complete" if output_file.exists() else "failed",
            cleanup_settings=settings,
            before_splat_count=before,
            after_splat_count=after,
            duration_seconds=round(perf_counter() - start, 6),
            warnings=warnings,
        )
    except Exception as exc:
        return CleanupRecord(
            patch_id=source.patch_id,
            source=source,
            output_file=output_file,
            status="failed",
            cleanup_settings=settings,
            before_splat_count=before,
            after_splat_count=ply_vertex_count(output_file) if output_file.exists() else None,
            duration_seconds=round(perf_counter() - start, 6),
            warnings=[str(exc), *warnings],
        )
