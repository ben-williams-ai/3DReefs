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
        lfs_config=tmp_path / "lfs.json",
    )

    assert command.args[:5] == ["LichtFeld-Studio", "-d", str(tmp_path / "dataset"), "-o", str(tmp_path / "out")]
    assert "--headless" in command.args
    assert command.args[-6:] == ["-i", "30000", "--max-cap", "1500000", "--strategy", "mcmc"]
    assert ["--config", str(tmp_path / "lfs.json")] == command.args[5:7]
