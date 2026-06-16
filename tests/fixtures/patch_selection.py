"""Compact scene builders for patch camera-selection tests."""

from __future__ import annotations

from pathlib import Path

from reefs.patches.artefacts import SparseImage, SparseObservation, SparsePoint, SparseScene
from reefs.patches.bounds import PatchBounds


def image(
    image_id: int,
    name: str,
    *,
    center: tuple[float, float, float],
    qvec: tuple[float, float, float, float] = (1, 0, 0, 0),
    camera_id: int = 1,
) -> SparseImage:
    """Return a small registered image fixture."""
    tvec = (-center[0], -center[1], -center[2])
    return SparseImage(
        image_id=image_id,
        camera_id=camera_id,
        name=name,
        qvec=qvec,
        tvec=tvec,
        center=center,
        header_line=f"{image_id} {qvec[0]} {qvec[1]} {qvec[2]} {qvec[3]} {tvec[0]} {tvec[1]} {tvec[2]} {camera_id} {name}",
        points_line="32 24 1",
        width=64,
        height=48,
        observations=(SparseObservation(32, 24, 1),),
    )


def scene(tmp_path: Path, images: list[SparseImage], points: list[SparsePoint]) -> SparseScene:
    """Return a small sparse scene fixture."""
    return SparseScene(
        model_dir=tmp_path,
        cameras_text="# CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n1 SIMPLE_PINHOLE 64 48 50 32 24\n",
        images=images,
        points=points,
    )


def point(point_id: int, xyz: tuple[float, float, float], image_ids: tuple[int, ...]) -> SparsePoint:
    """Return a sparse point observed by image point index zero."""
    track = " ".join(f"{image_id} 0" for image_id in image_ids)
    return SparsePoint(
        point_id=point_id,
        xyz=xyz,
        track_image_ids=image_ids,
        track_point2d_idxs=tuple(0 for _ in image_ids),
        line=f"{point_id} {xyz[0]} {xyz[1]} {xyz[2]} 255 255 255 0.1 {track}",
    )


def bounds() -> PatchBounds:
    """Return a default square patch around the optical axis."""
    return PatchBounds("p000", -1, 1, -1, 1, -1, 6, 0.1)
