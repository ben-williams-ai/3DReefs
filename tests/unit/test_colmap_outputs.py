"""Tests for COLMAP sparse output inspection."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from pathlib import Path

from reefs.colmap.outputs import list_sparse_models, select_sparse_model, summarise_sparse_model


def _write_model(path: Path, *, images: int, points: int) -> None:
    path.mkdir(parents=True)
    (path / "cameras.txt").write_text("1 OPENCV 10 10 1 1 1 1 0 0 0 0\n", encoding="utf-8")
    image_lines = []
    for image_id in range(1, images + 1):
        image_lines.append(f"{image_id} 1 0 0 0 0 0 0 1 image_{image_id}.jpg\n\n")
    (path / "images.txt").write_text("".join(image_lines), encoding="utf-8")
    point_lines = [f"{point_id} 0 0 0 255 255 255 1 1 0\n" for point_id in range(1, points + 1)]
    (path / "points3D.txt").write_text("".join(point_lines), encoding="utf-8")


def test_select_sparse_model_prefers_registered_images(tmp_path: Path) -> None:
    sparse = tmp_path / "sparse"
    _write_model(sparse / "0", images=2, points=10)
    _write_model(sparse / "1", images=4, points=1)

    selected = select_sparse_model(list_sparse_models(sparse))

    assert selected.model_id == "1"
    assert selected.registered_images == 4


def test_summarise_sparse_model_uses_pycolmap_for_binary_counts(tmp_path: Path, monkeypatch) -> None:
    model = tmp_path / "sparse"
    model.mkdir()
    (model / "cameras.bin").write_bytes(b"camera")
    (model / "images.bin").write_bytes(b"images")
    (model / "points3D.bin").write_bytes(b"points")

    class FakeReconstruction:
        def __init__(self, path: str) -> None:
            self.path = path
            self.images = {1: object(), 2: object(), 3: object()}
            self.points3D = {1: object(), 2: object(), 3: object(), 4: object()}

    monkeypatch.setitem(sys.modules, "pycolmap", SimpleNamespace(Reconstruction=FakeReconstruction))

    summary = summarise_sparse_model(model)

    assert summary.registered_images == 3
    assert summary.points3d == 4
