"""Tests for COLMAP command execution safeguards."""

from __future__ import annotations

import signal
import sys
from pathlib import Path

import pytest

from reefs.colmap.commands import ColmapCommand
from reefs.colmap.runner import IMAGE_METADATA_WRITE_FAILURE, ColmapCommandError, run_colmap_command


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


def _failing_undistorter(output: str, returncode: int = 1) -> ColmapCommand:
    return ColmapCommand(
        stage="sfm.undistort",
        args=[sys.executable, "-c", f"print({output!r}); raise SystemExit({returncode})"],
    )


def test_undistorter_classifies_exact_iptc_write_failure(tmp_path: Path) -> None:
    command = _failing_undistorter(
        "OpenImageIO assertion failed: encode_iptc_iim_one_tag: data != nullptr"
    )

    with pytest.raises(ColmapCommandError) as captured:
        run_colmap_command(command, log_path=tmp_path / "colmap.log")

    assert captured.value.failure_kind == IMAGE_METADATA_WRITE_FAILURE


@pytest.mark.parametrize(
    "output",
    [
        "OpenImageIO failed to read image metadata",
        "encode_iptc_iim_tag failed",
        "data != nullptr",
        "CUDA out of memory",
    ],
)
def test_undistorter_does_not_classify_similar_or_generic_failures(
    tmp_path: Path, output: str
) -> None:
    with pytest.raises(ColmapCommandError) as captured:
        run_colmap_command(_failing_undistorter(output), log_path=tmp_path / "colmap.log")

    assert captured.value.failure_kind is None


def test_successful_undistorter_does_not_raise_for_signature_text(tmp_path: Path) -> None:
    command = _failing_undistorter("encode_iptc_iim_one_tag", returncode=0)

    result = run_colmap_command(command, log_path=tmp_path / "colmap.log")

    assert result.returncode == 0


def test_signal_abort_does_not_activate_metadata_recovery(tmp_path: Path) -> None:
    command = ColmapCommand(
        stage="sfm.undistort",
        args=[
            sys.executable,
            "-c",
            "import os, signal; os.kill(os.getpid(), signal.SIGTERM)",
        ],
    )

    with pytest.raises(ColmapCommandError) as captured:
        run_colmap_command(command, log_path=tmp_path / "colmap.log")

    assert captured.value.failure_kind is None
