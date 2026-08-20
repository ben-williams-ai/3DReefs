"""Patch splat cleanup using wildflow."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from reefs.config.models import SplatCleanupConfig
from reefs.postprocess.artifacts import CleanupRecord, PatchTrainingSource, cleaned_output_for, ply_vertex_count
from reefs.postprocess.coverage import apply_complete_layout


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
        "boundary_method": "complete_layout_union",
    }


def _wildflow_cleanup_params(
    source: PatchTrainingSource,
    output_file: Path,
    config: SplatCleanupConfig,
) -> dict[str, object]:
    assert source.source_file is not None
    return {
        "input_file": str(source.source_file),
        "output_file": str(output_file),
        "max_area": config.max_area,
        "min_neighbors": config.min_neighbors,
        "radius": config.radius,
    }


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


def clean_patch_sources(
    *,
    sources: list[PatchTrainingSource],
    all_patches_dir: Path,
    config: SplatCleanupConfig,
) -> tuple[list[CleanupRecord], dict[str, object] | None]:
    """Clean patches, then trim only outside the complete scene footprint."""
    settings = cleanup_settings(config)
    records: list[CleanupRecord] = []
    intermediates: dict[str, Path] = {}
    outputs: dict[str, Path] = {}
    usable = [source for source in sources if source.usable and source.source_file is not None]
    try:
        for source in usable:
            assert source.source_file is not None
            intermediate = source.source_file.with_name(f"{source.source_file.stem}_wildflow_clean.ply")
            _run_wildflow_cleanup(
                {
                    "input_file": str(source.source_file),
                    "output_file": str(intermediate),
                    "max_area": config.max_area,
                    "min_neighbors": config.min_neighbors,
                    "radius": config.radius,
                }
            )
            intermediates[source.patch_id] = intermediate
            outputs[source.patch_id] = cleaned_output_for(source.source_file)
        audit = apply_complete_layout(intermediates, outputs, all_patches_dir)
        raw_counts = {
            source.patch_id: ply_vertex_count(source.source_file)
            for source in usable
            if source.source_file is not None
        }
        audit["raw_splat_count"] = sum(count or 0 for count in raw_counts.values())
        audit["exact_raw_inputs"] = [
            {"patch_id": source.patch_id, "path": str(source.source_file), "splat_count": raw_counts[source.patch_id]}
            for source in usable
        ]
        for source in sources:
            output = outputs.get(source.patch_id)
            records.append(
                CleanupRecord(
                    patch_id=source.patch_id,
                    source=source,
                    output_file=output,
                    status="complete" if output and output.exists() else "skipped",
                    cleanup_settings=settings,
                    before_splat_count=ply_vertex_count(source.source_file) if source.source_file else None,
                    after_splat_count=ply_vertex_count(output) if output and output.exists() else None,
                    warnings=[] if source in usable else [source.reason],
                )
            )
        return records, audit
    except Exception as exc:
        for source in sources:
            output = outputs.get(source.patch_id)
            records.append(
                CleanupRecord(
                    patch_id=source.patch_id,
                    source=source,
                    output_file=output,
                    status="failed" if source in usable else "skipped",
                    cleanup_settings=settings,
                    before_splat_count=ply_vertex_count(source.source_file) if source.source_file else None,
                    after_splat_count=ply_vertex_count(output) if output and output.exists() else None,
                    warnings=[str(exc)] if source in usable else [source.reason],
                )
            )
        return records, None
