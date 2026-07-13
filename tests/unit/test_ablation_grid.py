"""Tests for ablation sweep grid helpers."""

from __future__ import annotations

from pathlib import Path

from reefs.experiments.ablations.config import load_ablation_config
from reefs.experiments.ablations.grid import (
    build_sfm_jobs,
    build_splat_jobs,
    select_even_patch_ids,
)


def test_ablation_config_expands_expected_grid() -> None:
    config = load_ablation_config(Path("experiments/ablations/ablation_config.yml"))

    sfm_jobs = build_sfm_jobs(config)
    assert len(sfm_jobs) == 84
    assert len(build_splat_jobs(config)) == 189
    assert build_splat_jobs(config)[0].job_id == "splat_dataset1_best_res1024_patch200_500k"
    assert {job.variant.name for job in sfm_jobs} >= {
        "sfm_full_sift_global",
        "sfm_2048_sift_global",
        "sfm_1024_aliked_incremental",
    }
    variant = next(job.variant for job in sfm_jobs if job.variant.name == "sfm_1024_aliked_incremental")
    assert variant.overrides["advanced.sfm.feature_extraction.type"] == "ALIKED"
    assert variant.overrides["advanced.sfm.feature_extraction.aliked.model"] == "n32"
    assert variant.overrides["advanced.sfm.feature_extraction.max_image_size"] == 1024
    assert variant.overrides["advanced.sfm.reconstruction.backend"] == "incremental"
    assert variant.overrides["advanced.sfm.matching.mode"] == "sequential"
    assert "advanced.sfm.matching.cross_camera_pairs.enabled" not in variant.overrides
    assert "advanced.sfm.matching.cross_camera_pairs.run_matching_pass" not in variant.overrides


def test_select_even_patch_ids_matches_quantiles() -> None:
    selected = select_even_patch_ids([f"p{index:03d}" for index in range(20)], 5)

    assert selected == ["p000", "p005", "p010", "p014", "p019"]


def test_select_even_patch_ids_uses_all_when_short() -> None:
    assert select_even_patch_ids(["p002", "p000"], 5) == ["p000", "p002"]
