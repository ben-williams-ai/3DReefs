"""Tests for SfM step expansion and overlap helpers."""

from __future__ import annotations

from reefs.sfm.resume import sfm_step_overlaps
from reefs.sfm.validation import expand_sfm_steps, wants_sfm


def test_expand_sfm_steps_contains_default_stages() -> None:
    expanded = expand_sfm_steps(["sfm"])

    assert "sfm.extract" in expanded
    assert "sfm.undistort" in expanded


def test_wants_sfm_detects_sfm_substeps() -> None:
    assert wants_sfm(["foundation"]) is False
    assert wants_sfm(["sfm.preflight"]) is True


def test_sfm_step_overlap_matches_full_sfm_request() -> None:
    assert sfm_step_overlaps("sfm.extract", ["sfm"]) is True
    assert sfm_step_overlaps("sfm.extract", ["splat"]) is False
