"""Tests for ablation sweep grid helpers."""

from __future__ import annotations

from pathlib import Path

from reefs.experiments.ablations.config import load_ablation_config
from reefs.experiments.ablations.grid import build_sfm_jobs, build_splat_jobs, select_even_patch_ids


def test_ablation_config_expands_expected_grid() -> None:
    config = load_ablation_config(Path("experiments/ablations/ablation_config.yml"))

    assert len(build_sfm_jobs(config)) == 16
    assert len(build_splat_jobs(config)) == 36
    assert build_splat_jobs(config)[0].job_id == "splat_dataset1_best_patch200_1m"


def test_select_even_patch_ids_matches_quantiles() -> None:
    selected = select_even_patch_ids([f"p{index:03d}" for index in range(20)], 5)

    assert selected == ["p000", "p005", "p010", "p014", "p019"]


def test_select_even_patch_ids_uses_all_when_short() -> None:
    assert select_even_patch_ids(["p002", "p000"], 5) == ["p000", "p002"]
