"""Tests for config loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from reefs.config.loader import load_config


def test_load_config_valid(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
project:
  dir: /tmp/example
  recolour_images: false
tools:
  colmap_bin: colmap
  lfs_bin: LichtFeld-Studio
  splat_transform_bin: splat-transform
""".lstrip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.project.dir == Path("/tmp/example")
    assert config.project.recolour_images is False
    assert config.advanced.splat.train.num_iters == 30000


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        load_config(tmp_path / "missing.yml")


def test_load_config_malformed_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text("project: [", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid YAML"):
        load_config(config_path)


def test_load_config_wrong_type(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
project:
  dir: /tmp/example
  recolour_images: not-a-bool
tools:
  colmap_bin: colmap
  lfs_bin: LichtFeld-Studio
  splat_transform_bin: splat-transform
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Config validation failed"):
        load_config(config_path)


def test_example_config_has_mandatory_sections_before_advanced() -> None:
    text = Path("configs/example.yml").read_text(encoding="utf-8")
    config = yaml.safe_load(text)

    assert list(config) == ["project", "tools", "advanced"]
    assert set(config["advanced"]) == {"paths", "logging", "resume", "sfm", "splat"}
