"""Tests for config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from reefs.config.loader import load_config


def test_load_config_valid(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
project:
  dir: /tmp/example
  recolour_images: false
""".lstrip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.project.dir == Path("/tmp/example")
    assert config.project.recolour_images is False
    assert config.splat.train.num_iters == 30000


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
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Config validation failed"):
        load_config(config_path)
