"""Project path derivation helpers."""

from __future__ import annotations

from pathlib import Path

from reefs.config.models import DerivedPaths, PipelineConfig


def _resolve_under_project(project_dir: Path, value: Path) -> Path:
    if value.is_absolute():
        return value
    return project_dir / value


def derive_project_paths(config: PipelineConfig, project_dir_override: Path | None = None) -> DerivedPaths:
    """Derive normal project-local paths from project.dir."""
    project_dir = (project_dir_override or config.project.dir).expanduser().resolve()
    return DerivedPaths(
        project_dir=project_dir,
        raw_images=_resolve_under_project(project_dir, config.paths.raw_images_dir).resolve(),
        recoloured_images=_resolve_under_project(
            project_dir, config.paths.recoloured_images_dir
        ).resolve(),
        runs=_resolve_under_project(project_dir, config.paths.runs_dir).resolve(),
    )
