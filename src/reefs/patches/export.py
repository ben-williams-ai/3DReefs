"""Patch sparse model and selected-image export helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from reefs.io.yaml_json import write_json
from reefs.patches.artefacts import SparseScene
from reefs.patches.selection import SELECTOR_NAME, SELECTOR_VERSION, PatchSelection, selector_settings


def _filtered_points_line(points_line: str, kept_point_ids: set[int]) -> str:
    """Return an image points line with removed 3D point refs set to `-1`."""
    tokens = points_line.split()
    if not tokens:
        return points_line.rstrip("\n")
    output: list[str] = []
    for index in range(0, len(tokens), 3):
        try:
            point_id = int(tokens[index + 2])
        except (IndexError, ValueError):
            continue
        output.extend([tokens[index], tokens[index + 1], str(point_id if point_id in kept_point_ids else -1)])
    return " ".join(output)


def _write_sparse_subset(selection: PatchSelection, *, source_sparse: Path, destination: Path) -> int:
    """Write sparse text files for the selected images."""
    destination.mkdir(parents=True, exist_ok=True)
    cameras_text = (source_sparse / "cameras.txt").read_text(encoding="utf-8", errors="replace")
    (destination / "cameras.txt").write_text(cameras_text, encoding="utf-8")
    selected_ids = {image.image_id for image in selection.selected_images}
    kept_tracks_by_point: dict[int, list[tuple[int, int]]] = {}
    for point in selection.patch_points:
        kept_track = [(image_id, point2d_idx) for image_id, point2d_idx in point.track_pairs if image_id in selected_ids]
        if not kept_track:
            continue
        kept_tracks_by_point[point.point_id] = kept_track
    kept_point_ids = set(kept_tracks_by_point)
    image_lines = [
        "# Image list with two lines of data per image:\n",
        "# IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME\n",
    ]
    for image in sorted(selection.selected_images, key=lambda item: item.image_id):
        image_lines.append(image.header_line.rstrip("\n") + "\n")
        image_lines.append(_filtered_points_line(image.points_line, kept_point_ids) + "\n")
    (destination / "images.txt").write_text("".join(image_lines), encoding="utf-8")

    point_lines = [
        "# 3D point list with one line of data per point:\n",
        "# POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[]\n",
    ]
    sparse_point_count = 0
    for point in selection.patch_points:
        kept_track = kept_tracks_by_point.get(point.point_id, [])
        if not kept_track:
            continue
        parts = point.line.split()
        prefix = parts[:8]
        track_tokens: list[str] = []
        for image_id, point2d_idx in kept_track:
            track_tokens.extend([str(image_id), str(point2d_idx)])
        point_lines.append(" ".join([*prefix, *track_tokens]) + "\n")
        sparse_point_count += 1
    (destination / "points3D.txt").write_text("".join(point_lines), encoding="utf-8")
    return sparse_point_count


def write_sparse_subset_by_image_ids(
    *,
    scene: SparseScene,
    source_sparse: Path,
    destination: Path,
    kept_image_ids: set[int],
) -> int:
    """Write a sparse text subset for a set of registered image ids."""
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "cameras.txt").write_text(
        (source_sparse / "cameras.txt").read_text(encoding="utf-8", errors="replace"),
        encoding="utf-8",
    )
    image_lines = [
        "# Image list with two lines of data per image:\n",
        "# IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME\n",
    ]
    kept_point_ids: set[int] = set()
    kept_tracks_by_point: dict[int, list[tuple[int, int]]] = {}
    for point in scene.points:
        kept_track = [(image_id, point2d_idx) for image_id, point2d_idx in point.track_pairs if image_id in kept_image_ids]
        if not kept_track:
            continue
        kept_point_ids.add(point.point_id)
        kept_tracks_by_point[point.point_id] = kept_track
    for image in sorted(scene.images, key=lambda item: item.image_id):
        if image.image_id not in kept_image_ids:
            continue
        image_lines.append(image.header_line.rstrip("\n") + "\n")
        image_lines.append(_filtered_points_line(image.points_line, kept_point_ids) + "\n")
    (destination / "images.txt").write_text("".join(image_lines), encoding="utf-8")
    point_lines = [
        "# 3D point list with one line of data per point:\n",
        "# POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[]\n",
    ]
    count = 0
    for point in scene.points:
        kept_track = kept_tracks_by_point.get(point.point_id, [])
        if not kept_track:
            continue
        prefix = point.line.split()[:8]
        track_tokens: list[str] = []
        for image_id, point2d_idx in kept_track:
            track_tokens.extend([str(image_id), str(point2d_idx)])
        point_lines.append(" ".join([*prefix, *track_tokens]) + "\n")
        count += 1
    (destination / "points3D.txt").write_text("".join(point_lines), encoding="utf-8")
    return count


def _symlink_selected_images(*, image_root: Path, selection: PatchSelection, destination: Path) -> None:
    """Expose selected images for one patch via symlinks."""
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for image in selection.selected_images:
        target = destination / image.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to((image_root / image.name).resolve())


def export_patch_dataset(
    *,
    selection: PatchSelection,
    source_sparse: Path,
    image_root: Path,
    patch_dir: Path,
    source_run_id: str,
    patch_affecting_config: dict[str, object],
) -> dict[str, object]:
    """Export one patch dataset and metadata."""
    if patch_dir.exists():
        shutil.rmtree(patch_dir)
    sparse_dir = patch_dir / "sparse" / "0"
    selected_images_dir = patch_dir / "selected_images"
    diagnostics_dir = patch_dir / "patch_diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    sparse_point_count = _write_sparse_subset(selection, source_sparse=source_sparse, destination=sparse_dir)
    _symlink_selected_images(image_root=image_root, selection=selection, destination=selected_images_dir)
    invalid_reasons: list[str] = []
    if not selection.selected_images:
        invalid_reasons.append("no_selected_images")
    if sparse_point_count <= 0:
        invalid_reasons.append("no_sparse_points")
    metadata: dict[str, object] = {
        "patch_id": selection.bounds.patch_id,
        "source_run_id": source_run_id,
        "source_sparse": str(source_sparse),
        "patch_affecting_config": patch_affecting_config,
        "bounds": selection.bounds.as_dict(),
        "selected_images": [image.name for image in selection.selected_images],
        "selected_camera_count": len(selection.selected_images),
        "selected_local_count": len([image for image in selection.selected_images if image in selection.local_images]),
        "selected_support_count": len([image for image in selection.selected_images if image in selection.support_images]),
        "sparse_point_count": sparse_point_count,
        "selector": {
            "name": SELECTOR_NAME,
            "version": SELECTOR_VERSION,
            "signature": selector_settings(),
            "coverage": {},
            "warning_thresholds": {},
            "warning_flags": selection.warnings,
        },
        "invalid_reasons": invalid_reasons,
        "status": "invalid" if invalid_reasons else "valid",
        "warnings": selection.warnings,
    }
    write_json(patch_dir / "patch_metadata.json", metadata)
    return metadata
