"""Tests for top-level project config defaults."""

from __future__ import annotations

from pathlib import Path

from reefs.config.loader import load_config


def test_project_colour_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
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

    assert config.project.recolour_images is False
    assert config.project.start_sfm_immediately is True
