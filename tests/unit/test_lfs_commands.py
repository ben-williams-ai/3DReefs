"""Tests for LichtFeld Studio command construction."""

from __future__ import annotations

from pathlib import Path

from reefs.lfs.commands import build_lfs_train_command


def test_build_lfs_train_command_uses_old_pipeline_flags(tmp_path: Path) -> None:
    command = build_lfs_train_command(
        lfs_bin="LichtFeld-Studio",
        patch_id="p000",
        dataset_dir=tmp_path / "dataset",
        output_dir=tmp_path / "out",
        num_iters=30000,
        num_splats_per_patch=1500000,
        strategy="mcmc",
        headless=True,
        max_width=2048,
        lfs_config=tmp_path / "lfs.json",
    )

    assert command.args[:5] == ["LichtFeld-Studio", "-d", str(tmp_path / "dataset"), "-o", str(tmp_path / "out")]
    assert "--headless" in command.args
    assert command.args[-8:] == ["--max-width", "2048", "-i", "30000", "--max-cap", "1500000", "--strategy", "mcmc"]
    assert ["--config", str(tmp_path / "lfs.json")] == command.args[5:7]


def test_build_lfs_train_command_can_enable_eval(tmp_path: Path) -> None:
    command = build_lfs_train_command(
        lfs_bin="LichtFeld-Studio",
        patch_id="p000",
        dataset_dir=tmp_path / "dataset",
        output_dir=tmp_path / "out",
        num_iters=30000,
        num_splats_per_patch=2_000_000,
        strategy="mcmc",
        headless=True,
        max_width=None,
        lfs_config=None,
        eval_enabled=True,
        test_every=10,
    )

    assert "--eval" in command.args
    assert ["--test-every", "10"] == command.args[command.args.index("--test-every") : command.args.index("--test-every") + 2]
