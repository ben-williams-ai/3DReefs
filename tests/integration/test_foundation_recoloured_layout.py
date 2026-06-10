"""Integration test for recoloured image layout validation."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app
from tests.conftest import write_config


def test_recoloured_layout_must_mirror_raw_images(tmp_path: Path, fake_tool_factory) -> None:
    project = tmp_path / "project"
    (project / "raw_images").mkdir(parents=True)
    (project / "recoloured_images").mkdir()
    (project / "raw_images" / "image_0001.jpg").write_text("", encoding="utf-8")
    colmap = fake_tool_factory("colmap", "COLMAP 4.0.4")
    lfs = fake_tool_factory("lfs", "LichtFeld Studio v0.5.2")
    sog = fake_tool_factory("splat-transform", "splat-transform 1.0")
    config = write_config(
        tmp_path / "config.yml",
        project_dir=project,
        colmap_bin=colmap,
        lfs_bin=lfs,
        splat_transform_bin=sog,
        recolour_images=True,
    )

    result = CliRunner().invoke(app, ["--config", str(config)])

    assert result.exit_code != 0
    assert "missing recoloured images" in result.output
