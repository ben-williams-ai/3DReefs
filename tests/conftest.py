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
            "if [[ \"$1\" == \"--version\" || \"$1\" == \"-h\" ]]; then\n"
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


def write_test_jpeg(path: Path, *, width: int = 64, height: int = 48) -> Path:
    """Write a tiny JPEG-like file with a readable SOF0 dimension header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\xff\xd8"
        b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        + b"\xff\xc0\x00\x11\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
        + b"\xff\xd9"
    )
    return path
