"""Tests for final SOG export helpers."""

from __future__ import annotations

from pathlib import Path

from reefs.config.models import SogConfig
from reefs.postprocess.sog import build_sog_command


def test_build_sog_command_includes_filters_and_iterations(tmp_path: Path) -> None:
    command = build_sog_command(
        "splat-transform",
        tmp_path / "merged.ply",
        tmp_path / "merged.sog",
        SogConfig(iterations=12, filter_nan=True, filter_harmonics=2),
    )

    assert command == [
        "splat-transform",
        "-w",
        "--iterations",
        "12",
        str(tmp_path / "merged.ply"),
        "--filter-nan",
        "--filter-harmonics",
        "2",
        str(tmp_path / "merged.sog"),
    ]
