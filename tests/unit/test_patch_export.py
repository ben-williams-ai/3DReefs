"""Tests for patch dataset export."""

from __future__ import annotations

from pathlib import Path

from reefs.io.yaml_json import read_json
from reefs.patches.artefacts import read_sparse_scene_text
from reefs.patches.bounds import PatchBounds
from reefs.patches.export import export_patch_dataset
from reefs.patches.selection import select_patch_views
from tests.conftest import write_sparse_text_model, write_test_jpeg


def test_export_patch_dataset_writes_metadata_sparse_and_selected_images(tmp_path: Path) -> None:
    source_sparse = write_sparse_text_model(tmp_path / "sparse", ["image_0001.jpg"])
    image_root = tmp_path / "images"
    write_test_jpeg(image_root / "image_0001.jpg")
    scene = read_sparse_scene_text(source_sparse)
    selection = select_patch_views(scene, PatchBounds("p000", -1, 1, -1, 1, 0, 5, 0.1), max_cameras=10)

    metadata = export_patch_dataset(
        selection=selection,
        source_sparse=source_sparse,
        image_root=image_root,
        patch_dir=tmp_path / "patches" / "p000",
        source_run_id="run",
        patch_affecting_config={"patching": {"max_cameras": 10}},
    )

    patch_dir = tmp_path / "patches" / "p000"
    assert metadata["status"] == "valid"
    assert (patch_dir / "patch_metadata.json").exists()
    assert (patch_dir / "sparse" / "0" / "images.txt").exists()
    assert (patch_dir / "selected_images" / "image_0001.jpg").is_symlink()
    saved = read_json(patch_dir / "patch_metadata.json")
    assert saved["selected_images"] == ["image_0001.jpg"]
    assert saved["bounds"] == {
        "min_x": -1,
        "max_x": 1,
        "min_y": -1,
        "max_y": 1,
        "min_z": 0,
        "max_z": 5,
        "buffer": 0.1,
    }
