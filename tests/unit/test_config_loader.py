"""Tests for config loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from reefs.config.loader import load_config
from reefs.config.models import ColourRestorationMode


def test_load_config_valid(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
colour_restoration:
  mode: off
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

    assert config.project.dir == Path("/tmp/example")
    assert config.colour_restoration.mode == ColourRestorationMode.OFF
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
colour_restoration:
  mode: off
  overwrite: not-a-bool
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

    with pytest.raises(ValueError, match="Config validation failed"):
        load_config(config_path)


def test_load_config_missing_colour_restoration_block_fails(tmp_path: Path) -> None:
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

    with pytest.raises(ValueError, match="missing required top-level colour_restoration block"):
        load_config(config_path)


def test_load_config_legacy_project_recolour_images_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
colour_restoration:
  mode: off
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

    with pytest.raises(ValueError, match="project.recolour_images is no longer supported"):
        load_config(config_path)


def test_load_config_legacy_project_start_sfm_immediately_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
colour_restoration:
  mode: manual
project:
  dir: /tmp/example
  start_sfm_immediately: true
tools:
  colmap_bin: colmap
  lfs_bin: LichtFeld-Studio
  splat_transform_bin: splat-transform
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="project.start_sfm_immediately is no longer supported"):
        load_config(config_path)


def test_load_config_invalid_colour_restoration_mode_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
colour_restoration:
  mode: greyworld
project:
  dir: /tmp/example
tools:
  colmap_bin: colmap
  lfs_bin: LichtFeld-Studio
  splat_transform_bin: splat-transform
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Config validation failed"):
        load_config(config_path)


def test_load_config_expands_environment_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yml"
    monkeypatch.setenv("REEF_PROJECT_DIR", "/tmp/example")
    monkeypatch.setenv("COLMAP_BIN", "/opt/colmap")
    monkeypatch.setenv("VOCAB_TREE_PATH", "/opt/vocab.bin")
    config_path.write_text(
        """
colour_restoration:
  mode: off
  overwrite: false
  start_sfm_immediately: true

project:
  dir: ${REEF_PROJECT_DIR}
tools:
  colmap_bin: ${COLMAP_BIN}
  lfs_bin: LichtFeld-Studio
  splat_transform_bin: splat-transform
  vocab_tree_path: ${VOCAB_TREE_PATH}
""".lstrip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.project.dir == Path("/tmp/example")
    assert config.tools.colmap_bin == "/opt/colmap"
    assert config.tools.vocab_tree_path == Path("/opt/vocab.bin")


def test_example_config_has_mandatory_sections_before_advanced() -> None:
    text = Path("configs/example.yml").read_text(encoding="utf-8")
    config = yaml.safe_load(text)

    assert list(config) == ["colour_restoration", "project", "tools", "advanced"]
    assert set(config["advanced"]) == {"paths", "logging", "resume", "sfm", "splat", "eval"}


@pytest.mark.parametrize(
    "config_path",
    [
        Path("configs/example.yml"),
        Path("configs/test.yml"),
        *sorted(Path("configs/datasets").glob("*.yml")),
        *sorted(Path("configs/datasets").glob("*.yaml")),
    ],
)
def test_maintained_example_configs_load(config_path: Path) -> None:
    config = load_config(config_path)

    assert config.colour_restoration.mode in {
        ColourRestorationMode.OFF,
        ColourRestorationMode.GRAY_WORLD,
        ColourRestorationMode.MANUAL,
        ColourRestorationMode.PROFILE,
    }
