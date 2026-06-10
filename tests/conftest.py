"""Shared pytest fixtures for 3DReefs tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fake_tool_factory(tmp_path: Path):
    """Create executable fake external tools."""

    def make_tool(name: str, version: str = "tool 1.0") -> Path:
        path = tmp_path / name
        path.write_text(
            "#!/usr/bin/env bash\n"
            "if [[ \"$1\" == \"--version\" ]]; then\n"
            f"  echo \"{version}\"\n"
            "else\n"
            "  echo \"help\"\n"
            "fi\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    return make_tool


def write_config(
    path: Path,
    *,
    project_dir: Path,
    colmap_bin: Path,
    lfs_bin: Path,
    splat_transform_bin: Path,
    recolour_images: bool = False,
) -> Path:
    """Write a minimal test config."""
    path.write_text(
        f"""
project:
  dir: {project_dir}
  recolour_images: {str(recolour_images).lower()}
tools:
  colmap_bin: {colmap_bin}
  lfs_bin: {lfs_bin}
  splat_transform_bin: {splat_transform_bin}
advanced:
  splat:
    sog:
      enabled: true
""".lstrip(),
        encoding="utf-8",
    )
    return path
