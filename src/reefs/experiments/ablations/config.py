"""Configuration loading for ablation sweeps."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from reefs.io.yaml_json import read_yaml


@dataclass(frozen=True)
class DatasetSpec:
    """One dataset available to the ablation sweep."""

    name: str
    config: Path
    project_dir: Path


@dataclass(frozen=True)
class SfMVariant:
    """One SfM ablation variant."""

    name: str
    description: str
    overrides: dict[str, object] = field(default_factory=dict)
    sweep_dimensions: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AblationConfig:
    """Top-level ablation sweep configuration."""

    output_root: Path
    datasets: list[DatasetSpec]
    sfm_variants: list[SfMVariant]
    aims_baseline_overrides: dict[str, object]
    patch_sizes: list[int]
    splat_counts: list[int]
    max_widths: list[int]
    validation_patch_count: int
    holdout_fraction: float
    validation_target_image_source: str
    validation_full_resolution_undistorted_images_dir: Path | None
    validation_allow_full_resolution_target: bool
    sfm_timeout_hours: float
    default_patch_size: int
    default_splat_count: int
    run_validation_splats_for_sfm: bool


def load_ablation_config(path: Path, *, repo_root: Path | None = None) -> AblationConfig:
    """Load an ablation config YAML file."""
    root = repo_root or Path.cwd()
    data = read_yaml(path)
    datasets = [
        DatasetSpec(
            name=str(item["name"]),
            config=_resolve_path(root, item["config"]),
            project_dir=_resolve_path(root, item["project_dir"]),
        )
        for item in data.get("datasets", [])
    ]
    sfm_variants = [
        SfMVariant(
            name=str(item["name"]),
            description=str(item.get("description", item["name"])),
            overrides=dict(item.get("overrides") or {}),
            sweep_dimensions=dict(item.get("sweep_dimensions") or {}),
        )
        for item in data.get("sfm_variants", [])
    ]
    splat = dict(data.get("splat_grid") or {})
    validation = dict(data.get("validation") or {})
    full_res_dir = validation.get("full_resolution_undistorted_images_dir")
    target_image_source = _normalise_validation_target(
        str(validation.get("target_image_source", "full_resolution_undistorted"))
    )
    allow_full_resolution_target = bool(
        validation.get("allow_full_resolution_target", target_image_source == "full_resolution_undistorted")
    )
    if target_image_source == "full_resolution_undistorted" and not allow_full_resolution_target:
        raise ValueError(
            "validation.target_image_source=full_resolution_undistorted is diagnostic-only for ablations. "
            "Set validation.allow_full_resolution_target: true to opt in explicitly."
        )
    return AblationConfig(
        output_root=_resolve_path(root, data.get("output_root", "data/experiments/ablations")),
        datasets=datasets,
        sfm_variants=sfm_variants,
        aims_baseline_overrides=dict(data.get("aims_baseline_overrides") or {}),
        patch_sizes=[int(value) for value in splat.get("patch_sizes", [200, 400, 800])],
        splat_counts=[int(value) for value in splat.get("splat_counts", [1_000_000, 2_000_000, 3_000_000])],
        max_widths=[int(value) for value in splat.get("max_widths", [1024, 2048, 4096])],
        validation_patch_count=int(validation.get("patch_count", 5)),
        holdout_fraction=float(validation.get("holdout_fraction", 0.10)),
        validation_target_image_source=target_image_source,
        validation_full_resolution_undistorted_images_dir=(
            _resolve_path(root, full_res_dir) if full_res_dir is not None else None
        ),
        validation_allow_full_resolution_target=allow_full_resolution_target,
        sfm_timeout_hours=float(data.get("sfm_timeout_hours", 20)),
        default_patch_size=int(data.get("default_patch_size", 400)),
        default_splat_count=int(data.get("default_splat_count", 1_000_000)),
        run_validation_splats_for_sfm=bool(data.get("run_validation_splats_for_sfm", True)),
    )


def _resolve_path(root: Path, value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def _normalise_validation_target(source: str) -> str:
    if source in {"resized_undistorted", "patch_undistorted"}:
        return "training_undistorted"
    return source
