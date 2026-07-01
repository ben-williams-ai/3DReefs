"""Ablation sweep grid expansion."""

from __future__ import annotations

from dataclasses import dataclass

from reefs.experiments.ablations.config import AblationConfig, DatasetSpec, SfMVariant


@dataclass(frozen=True)
class SfMJob:
    """One SfM ablation job."""

    dataset: DatasetSpec
    variant: SfMVariant
    patch_size: int
    splat_count: int

    @property
    def job_id(self) -> str:
        return f"sfm_{self.dataset.name}_{self.variant.name}"


@dataclass(frozen=True)
class SplatJob:
    """One splat-grid ablation job."""

    dataset: DatasetSpec
    patch_size: int
    splat_count: int
    max_width: int | None
    sfm_variant: str

    @property
    def job_id(self) -> str:
        splats = f"{self.splat_count // 1_000_000}m"
        suffix = f"_w{self.max_width}" if self.max_width else ""
        return f"splat_{self.dataset.name}_{self.sfm_variant}_patch{self.patch_size}_{splats}{suffix}"


def build_sfm_jobs(config: AblationConfig) -> list[SfMJob]:
    """Return all configured SfM jobs."""
    return [
        SfMJob(
            dataset=dataset,
            variant=variant,
            patch_size=config.default_patch_size,
            splat_count=config.default_splat_count,
        )
        for dataset in config.datasets
        for variant in config.sfm_variants
    ]


def build_splat_jobs(config: AblationConfig, *, sfm_variant: str = "best") -> list[SplatJob]:
    """Return all configured splat jobs."""
    max_widths: list[int | None] = config.max_widths or [None]
    return [
        SplatJob(
            dataset=dataset,
            patch_size=patch_size,
            splat_count=splat_count,
            max_width=max_width,
            sfm_variant=sfm_variant,
        )
        for dataset in config.datasets
        for patch_size in config.patch_sizes
        for splat_count in config.splat_counts
        for max_width in max_widths
    ]


def select_even_patch_ids(available_patch_ids: list[str], count: int) -> list[str]:
    """Select up to count patch ids evenly across the sorted patch list."""
    ordered = sorted(available_patch_ids)
    if count <= 0 or not ordered:
        return []
    if len(ordered) <= count:
        return ordered
    if count == 1:
        return [ordered[len(ordered) // 2]]
    indexes = [round(index * (len(ordered) - 1) / (count - 1)) for index in range(count)]
    selected: list[str] = []
    for index in indexes:
        patch_id = ordered[index]
        if patch_id not in selected:
            selected.append(patch_id)
    return selected
