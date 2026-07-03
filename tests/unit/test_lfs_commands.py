"""Tests for LichtFeld Studio command construction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from reefs.lfs.commands import build_lfs_train_command, write_lfs_eval_config


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
    assert "--no-save-eval-images" in command.args
    assert ["--test-every", "10"] == command.args[command.args.index("--test-every") : command.args.index("--test-every") + 2]


def test_write_lfs_eval_config_preserves_base_and_overrides_cadence(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    base.write_text('{"strategy": "mcmc", "eval_steps": [7000], "enable_eval": false}', encoding="utf-8")

    written = write_lfs_eval_config(
        path=tmp_path / "attempt" / "lfs_eval_config.json",
        base_config=base,
        eval_steps=[5000, 10000],
        save_steps=[5000, 10000],
        headless=True,
        eval_enabled=True,
        save_eval_images=False,
    )

    data = json.loads(written.read_text(encoding="utf-8"))
    assert data["strategy"] == "mcmc"
    assert data["eval_steps"] == [5000, 10000]
    assert data["save_steps"] == [5000, 10000]
    assert data["enable_eval"] is True
    assert data["enable_save_eval_images"] is False
    assert data["headless"] is True


def test_write_lfs_eval_config_requires_base_config(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="advanced.splat.train.lfs_config"):
        write_lfs_eval_config(
            path=tmp_path / "lfs_eval_config.json",
            base_config=None,
            eval_steps=[500],
            save_steps=[500],
            headless=True,
        )
