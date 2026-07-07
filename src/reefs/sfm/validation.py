"""SfM stage naming and output path helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reefs.runs.manifest import RunPaths


SFM_ALL_STAGES = [
    "sfm.preflight",
    "sfm.intrinsics",
    "sfm.extract",
    "sfm.match",
    "sfm.match.sequential",
    "sfm.match.vocab_tree",
    "sfm.match.exhaustive",
    "sfm.match.spatial",
    "sfm.match.cross_camera_pairs",
    "sfm.reconstruct",
    "sfm.refine",
    "sfm.undistort",
]


def expand_sfm_steps(requested_steps: list[str]) -> list[str]:
    """Expand `sfm` to all default SfM stages."""
    expanded: list[str] = []
    for step in requested_steps:
        if step == "sfm":
            expanded.extend(SFM_ALL_STAGES)
        else:
            expanded.append(step)
    return expanded


def wants_sfm(requested_steps: list[str]) -> bool:
    """Return whether any requested step belongs to Feature 2 SfM."""
    return any(step == "sfm" or step.startswith("sfm.") for step in requested_steps)


@dataclass(frozen=True)
class SfMPaths:
    """Filesystem paths for SfM outputs in one run."""

    root: Path
    database: Path
    sparse: Path
    selected_sparse: Path
    selected_sparse_text: Path
    refined_sparse: Path
    cross_camera_pairs: Path
    undistorted: Path
    full_resolution_undistorted: Path
    dense: Path
    colmap_log: Path


def create_sfm_paths(run_paths: RunPaths) -> SfMPaths:
    """Create SfM output directories and return path bundle."""
    root = run_paths.run_dir / "sfm"
    paths = SfMPaths(
        root=root,
        database=root / "database.db",
        sparse=root / "sparse",
        selected_sparse=root / "selected_sparse",
        selected_sparse_text=root / "selected_sparse_txt",
        refined_sparse=root / "refined_sparse",
        cross_camera_pairs=root / "cross_camera_pairs",
        undistorted=root / "undistorted",
        full_resolution_undistorted=root / "undistorted_full_resolution",
        dense=root / "dense",
        colmap_log=run_paths.logs_dir / "colmap.log",
    )
    for path in [paths.root, paths.sparse]:
        path.mkdir(parents=True, exist_ok=True)
    return paths
