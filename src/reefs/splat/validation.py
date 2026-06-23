"""Splat source reconstruction validation helpers."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path

from reefs.colour.pipeline import colour_state_path, corrected_tree_status
from reefs.colour.state import ColourStatus, maybe_load_state
from reefs.patches.artefacts import SparseModelFiles, detect_sparse_model_files, read_image_names_text
from reefs.colour.ordering import natural_key
from reefs.config.models import ColourRestorationMode
from reefs.preflight.images import IMAGE_SUFFIXES
from reefs.runs.manifest import RunPaths


SPLAT_ALL_STAGES = [
    "splat.preflight",
    "splat.outlier_filter",
    "splat.patch",
    "splat.train",
]

SPLAT_POSTPROCESS_STAGES = [
    "splat.cleanup",
    "splat.merge",
    "splat.sog",
]


def expand_splat_steps(requested_steps: list[str]) -> list[str]:
    """Expand splat aliases to concrete stages."""
    expanded: list[str] = []
    for step in requested_steps:
        if step == "splat":
            expanded.extend(SPLAT_ALL_STAGES)
        elif step == "splat.postprocess":
            expanded.extend(SPLAT_POSTPROCESS_STAGES)
        else:
            expanded.append(step)
    return expanded


def wants_splat(requested_steps: list[str]) -> bool:
    """Return whether any requested step belongs to Feature 3 splatting."""
    return any(step == "splat" or step.startswith("splat.") for step in requested_steps)


def wants_splat_training(requested_steps: list[str]) -> bool:
    """Return whether requested splat steps include LFS training."""
    expanded = set(expand_splat_steps(requested_steps))
    return "splat" in requested_steps or "splat.train" in expanded


@dataclass(frozen=True)
class SplatPaths:
    """Filesystem paths for splat outputs in one run."""

    root: Path
    outlier_filter: Path
    filtered_sparse: Path
    patches: Path
    training: Path
    postprocess: Path
    postprocess_manifest: Path
    merged: Path
    merged_ply: Path
    sog: Path
    final_sog: Path
    lfs_log: Path
    splat_transform_log: Path


def create_splat_paths(run_paths: RunPaths) -> SplatPaths:
    """Create splat output directories and return path bundle."""
    root = run_paths.run_dir / "splat"
    paths = SplatPaths(
        root=root,
        outlier_filter=root / "outlier_filter",
        filtered_sparse=root / "outlier_filter" / "filtered_sparse",
        patches=root / "patches",
        training=root / "training",
        postprocess=root / "postprocess",
        postprocess_manifest=root / "postprocess" / "postprocess_manifest.json",
        merged=root / "merged",
        merged_ply=root / "merged" / "merged_splat.ply",
        sog=root / "merged",
        final_sog=root / "merged" / "merged_splat.sog",
        lfs_log=run_paths.logs_dir / "lfs.log",
        splat_transform_log=run_paths.logs_dir / "splat_transform.log",
    )
    root.mkdir(parents=True, exist_ok=True)
    return paths


@dataclass(frozen=True)
class SplatSourcePaths:
    """Feature 2 outputs used as Feature 3 inputs."""

    images_dir: Path
    sparse_dir: Path
    image_source: str = "raw"
    geometry_images_dir: Path | None = None

    def as_dict(self) -> dict[str, str]:
        """Return serialisable source paths."""
        return {
            "images_dir": str(self.images_dir),
            "sparse_dir": str(self.sparse_dir),
            "image_source": self.image_source,
            "geometry_images_dir": str(self.geometry_images_dir or self.images_dir),
        }


@dataclass(frozen=True)
class SplatSourceValidation:
    """Validated source reconstruction information."""

    paths: SplatSourcePaths
    sparse_files: SparseModelFiles
    image_count: int
    sparse_image_count: int
    point_count: int
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable validation result."""
        return {
            "paths": self.paths.as_dict(),
            "sparse_files": self.sparse_files.as_dict(),
            "image_count": self.image_count,
            "sparse_image_count": self.sparse_image_count,
            "point_count": self.point_count,
            "warnings": self.warnings,
        }


def validate_pycolmap_available() -> None:
    """Fail early when pycolmap is not importable."""
    if importlib.util.find_spec("pycolmap") is None:
        raise ValueError("pycolmap is required for splat patching but is not installed")


def default_splat_source_paths(run_paths: RunPaths) -> SplatSourcePaths:
    """Return the default Feature 2 undistorted source paths."""
    undistorted = run_paths.run_dir / "sfm" / "undistorted"
    return SplatSourcePaths(images_dir=undistorted / "images", sparse_dir=undistorted / "sparse")


def _colour_restored_splat_paths(run_paths: RunPaths, *, allow_skipped_raw: bool = False) -> SplatSourcePaths:
    """Return colour-restored splatting image paths when complete state permits it."""
    default = default_splat_source_paths(run_paths)
    state = maybe_load_state(colour_state_path(run_paths.run_dir))
    if state is None:
        raise ValueError("Colour restoration state is missing; restored images cannot be used for splatting")
    if allow_skipped_raw and state.status == ColourStatus.SKIPPED:
        return default
    if state.status != ColourStatus.COMPLETE or state.active_session:
        raise ValueError("Colour restoration is not complete; restored images cannot be used for splatting")
    if state.restoration_mode not in {ColourRestorationMode.GRAY_WORLD.value, ColourRestorationMode.MANUAL.value}:
        raise ValueError("Colour restoration state has an incompatible mode for splatting")
    restored_root = state.splat_images_path or state.output_recoloured_root
    status = corrected_tree_status(raw_images=state.source_raw_root, recoloured_images=restored_root)
    if not status.complete:
        raise ValueError("Colour-restored image tree is incomplete or inconsistent")
    return SplatSourcePaths(
        images_dir=restored_root,
        sparse_dir=default.sparse_dir,
        image_source="recoloured",
        geometry_images_dir=default.images_dir,
    )


def _image_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES),
        key=lambda path: natural_key(path.relative_to(root)),
    )


def validate_splat_source(run_paths: RunPaths, *, config=None) -> SplatSourceValidation:
    """Validate completed undistorted SfM outputs before splat work starts."""
    source_paths = default_splat_source_paths(run_paths)
    if config is not None and config.colour_restoration.mode == ColourRestorationMode.GRAY_WORLD:
        source_paths = _colour_restored_splat_paths(run_paths)
    elif config is not None and config.colour_restoration.mode == ColourRestorationMode.MANUAL:
        source_paths = _colour_restored_splat_paths(run_paths, allow_skipped_raw=True)
    geometry_images_dir = source_paths.geometry_images_dir or source_paths.images_dir
    if not geometry_images_dir.exists():
        raise ValueError(f"COLMAP undistorted images directory is missing: {geometry_images_dir}")
    geometry_image_files = _image_files(geometry_images_dir)
    if not geometry_image_files:
        raise ValueError(f"COLMAP undistorted images directory contains no images: {geometry_images_dir}")
    if not source_paths.images_dir.exists():
        raise ValueError(f"Splat image directory is missing: {source_paths.images_dir}")
    image_files = _image_files(source_paths.images_dir)
    if not image_files:
        raise ValueError(f"Splat image directory contains no images: {source_paths.images_dir}")
    sparse_files = detect_sparse_model_files(source_paths.sparse_dir)
    if sparse_files.summary.registered_images <= 0:
        raise ValueError(f"COLMAP undistorted sparse model contains no registered images: {source_paths.sparse_dir}")
    if sparse_files.summary.points3d <= 0:
        raise ValueError(f"COLMAP undistorted sparse model contains no 3D points: {source_paths.sparse_dir}")

    warnings: list[str] = []
    sparse_names = read_image_names_text(sparse_files.images)
    if sparse_names:
        image_names = {str(path.relative_to(source_paths.images_dir)) for path in image_files}
        missing_images = sorted(set(sparse_names) - image_names, key=natural_key)
        extra_images = sorted(image_names - set(sparse_names), key=natural_key)
        if missing_images:
            raise ValueError(
                "COLMAP sparse model references undistorted images that are missing: "
                + ", ".join(missing_images[:10])
            )
        if extra_images:
            warnings.append(
                "Undistorted image directory contains images not registered in sparse model: "
                + ", ".join(extra_images[:10])
            )

    return SplatSourceValidation(
        paths=source_paths,
        sparse_files=sparse_files,
        image_count=len(image_files),
        sparse_image_count=sparse_files.summary.registered_images,
        point_count=sparse_files.summary.points3d,
        warnings=warnings,
    )
