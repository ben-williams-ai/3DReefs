"""Tests for COLMAP command execution safeguards."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from reefs.colmap.commands import ColmapCommand
from reefs.colmap.runner import ColmapCommandError, run_colmap_command


def test_cross_camera_pair_import_fails_on_missing_image_log(tmp_path: Path) -> None:
    command = ColmapCommand(
        stage="sfm.match.cross_camera_pairs",
        args=[
            sys.executable,
            "-c",
            "print('E20260702 pairing.cc:78] Image cam1/foo does not exist.')",
        ],
    )

    with pytest.raises(ColmapCommandError, match="pair list references missing images"):
        run_colmap_command(command, log_path=tmp_path / "colmap.log")
