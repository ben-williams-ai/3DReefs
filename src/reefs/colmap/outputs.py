"""COLMAP sparse output inspection helpers."""

from __future__ import annotations

import importlib
import re
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SparseModelSummary:
    """Summary of one COLMAP sparse model."""

    model_id: str
    path: Path
    registered_images: int
    points3d: int
    selected: bool = False

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable sparse model summary."""
        return {
            "model_id": self.model_id,
            "path": str(self.path),
            "registered_images": self.registered_images,
            "points3d": self.points3d,
            "selected": self.selected,
        }


def _count_binary_records(path: Path) -> int:
    """Return the record count stored in a COLMAP binary model file."""
    if not path.exists() or path.stat().st_size == 0:
        return 0
    if path.stat().st_size < 8:
        return 1
    return struct.unpack("<Q", path.read_bytes()[:8])[0]


def _summarise_binary_model(model_path: Path) -> tuple[int, int] | None:
    """Return exact binary sparse counts using pycolmap when available."""
    if not (model_path / "images.bin").exists() and not (model_path / "points3D.bin").exists():
        return None
    try:
        pycolmap = importlib.import_module("pycolmap")
        reconstruction = pycolmap.Reconstruction(str(model_path))
    except Exception:
        return None
    return len(reconstruction.images), len(reconstruction.points3D)


def count_images_text(path: Path) -> int:
    """Count registered images in a COLMAP `images.txt` file."""
    if not path.exists():
        return 0
    image_header = re.compile(
        r"^\s*\d+\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s+[-+0-9.eE]+"
        r"\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s+\d+\s+.+$"
    )
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and image_header.match(stripped):
                count += 1
    return count


def count_points_text(path: Path) -> int:
    """Count points in a COLMAP `points3D.txt` file."""
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                count += 1
    return count


def count_linked_points2d_text(path: Path) -> int:
    """Count image observations linked to 3D points in a COLMAP `images.txt` file."""
    if not path.exists():
        return 0
    linked = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        while True:
            image_line = handle.readline()
            if not image_line:
                break
            stripped = image_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            points_line = handle.readline()
            for point_id in points_line.split()[2::3]:
                try:
                    if int(point_id) >= 0:
                        linked += 1
                except ValueError:
                    continue
    return linked


def summarise_sparse_model(model_path: Path) -> SparseModelSummary:
    """Summarise one sparse model directory."""
    registered_images = count_images_text(model_path / "images.txt")
    points3d = count_points_text(model_path / "points3D.txt")
    if registered_images == 0 or points3d == 0:
        binary_counts = _summarise_binary_model(model_path)
        if binary_counts:
            registered_images = registered_images or binary_counts[0]
            points3d = points3d or binary_counts[1]
    if registered_images == 0:
        registered_images = _count_binary_records(model_path / "images.bin")
    if points3d == 0:
        points3d = _count_binary_records(model_path / "points3D.bin")
    return SparseModelSummary(
        model_id=model_path.name,
        path=model_path,
        registered_images=registered_images,
        points3d=points3d,
    )


def list_sparse_models(sparse_root: Path) -> list[SparseModelSummary]:
    """List sparse model directories under a COLMAP output root."""
    if not sparse_root.exists():
        return []
    model_dirs = sorted(path for path in sparse_root.iterdir() if path.is_dir())
    if (sparse_root / "cameras.txt").exists() or (sparse_root / "cameras.bin").exists():
        model_dirs = [sparse_root]
    return [summarise_sparse_model(path) for path in model_dirs]


def select_sparse_model(summaries: list[SparseModelSummary]) -> SparseModelSummary:
    """Select the sparse model with the most registered images, then points."""
    if not summaries:
        raise ValueError("No sparse reconstruction models were produced")
    selected = sorted(summaries, key=lambda item: (-item.registered_images, -item.points3d, item.model_id))[0]
    return SparseModelSummary(
        model_id=selected.model_id,
        path=selected.path,
        registered_images=selected.registered_images,
        points3d=selected.points3d,
        selected=True,
    )
