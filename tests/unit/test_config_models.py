"""Tests for top-level project config defaults."""

from __future__ import annotations

from pathlib import Path

import pytest

from reefs.config.loader import load_config
from reefs.config.models import ColourRestorationMode, PipelineConfig


def test_colour_restoration_defaults_to_off_when_mode_omitted(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
colour_restoration:
  overwrite: false
  start_sfm_immediately: true

project:
  dir: /tmp/example
tools:
  colmap_bin: colmap
  lfs_bin: LichtFeld-Studio
  splat_transform_bin: splat-transform
""".lstrip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.colour_restoration.mode == ColourRestorationMode.OFF
    assert config.colour_restoration.overwrite is False
    assert config.colour_restoration.start_sfm_immediately is True


@pytest.mark.parametrize(
    "mode",
    [
        ColourRestorationMode.OFF,
        ColourRestorationMode.GRAY_WORLD,
        ColourRestorationMode.MANUAL,
    ],
)
def test_colour_restoration_valid_modes(tmp_path: Path, mode: ColourRestorationMode) -> None:
    config = PipelineConfig.model_validate(
        {
            "colour_restoration": {"mode": mode.value},
            "project": {"dir": tmp_path},
            "tools": {
                "colmap_bin": "colmap",
                "lfs_bin": "LichtFeld-Studio",
                "splat_transform_bin": "splat-transform",
            },
        }
    )

    assert config.colour_restoration.mode == mode
