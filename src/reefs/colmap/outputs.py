"""COLMAP sparse output inspection helpers."""

from __future__ import annotations

import re
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
    """Return 1 when a binary COLMAP file exists but exact counting is unavailable."""
    return 1 if path.exists() and path.stat().st_size > 0 else 0


def count_images_text(path: Path) -> int:
    """Count registered images in a COLMAP `images.txt` file."""
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and re.match(r"^\d+\s", stripped):
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


def summarise_sparse_model(model_path: Path) -> SparseModelSummary:
    """Summarise one sparse model directory."""
    registered_images = count_images_text(model_path / "images.txt")
    points3d = count_points_text(model_path / "points3D.txt")
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
    """Select the sparse model with the most registered images."""
    if not summaries:
        raise ValueError("No sparse reconstruction models were produced")
    selected = sorted(summaries, key=lambda item: (-item.registered_images, item.model_id))[0]
    return SparseModelSummary(
        model_id=selected.model_id,
        path=selected.path,
        registered_images=selected.registered_images,
        points3d=selected.points3d,
        selected=True,
    )
