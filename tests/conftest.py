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
    colour_restoration_mode: str = "off",
    colour_overwrite: bool = False,
    start_sfm_immediately: bool = True,
) -> Path:
    """Write a minimal test config."""
    path.write_text(
        f"""
colour_restoration:
  mode: {colour_restoration_mode}
  overwrite: {str(colour_overwrite).lower()}
  start_sfm_immediately: {str(start_sfm_immediately).lower()}

project:
  dir: {project_dir}
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


@pytest.fixture
def require_pycolmap():
    """Skip a test when pycolmap is unavailable in the local environment."""
    return pytest.importorskip("pycolmap")


def write_sparse_text_model(path: Path, image_names: list[str] | None = None) -> Path:
    """Write a tiny COLMAP text sparse model for tests."""
    path.mkdir(parents=True, exist_ok=True)
    names = image_names or ["image_0001.jpg"]
    (path / "cameras.txt").write_text(
        "# Camera list with one line of data per camera:\n"
        "# CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n"
        "1 SIMPLE_PINHOLE 64 48 50 32 24\n",
        encoding="utf-8",
    )
    image_lines: list[str] = [
        "# Image list with two lines of data per image:\n",
        "# IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME\n",
    ]
    for index, name in enumerate(names, start=1):
        image_lines.append(f"{index} 1 0 0 0 {index - 1}.0 0 -3.5 1 {name}\n")
        image_lines.append("32 24 1\n")
    (path / "images.txt").write_text("".join(image_lines), encoding="utf-8")
    (path / "points3D.txt").write_text(
        "# 3D point list with one line of data per point:\n"
        "# POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[]\n"
        f"1 0 0 4 255 255 255 0.5 {' '.join(f'{i} 0' for i in range(1, len(names) + 1))}\n",
        encoding="utf-8",
    )
    return path


def write_undistorted_sfm_fixture(
    run_dir: Path,
    *,
    image_names: list[str] | None = None,
) -> Path:
    """Create minimal Feature 2 undistorted outputs for splat tests."""
    names = image_names or ["image_0001.jpg"]
    images_dir = run_dir / "sfm" / "undistorted" / "images"
    for name in names:
        write_test_jpeg(images_dir / name)
    return write_sparse_text_model(run_dir / "sfm" / "undistorted" / "sparse", names)
