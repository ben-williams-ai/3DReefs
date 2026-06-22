"""Ordering audit coverage across colour, SfM, patch, and splat paths."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from reefs.colour.ordering import build_image_sequence
from reefs.patches.artefacts import SparseImage
from reefs.patches.bounds import PatchBounds
from reefs.patches.export import export_patch_dataset
from reefs.patches.selection import PatchSelection
from reefs.preflight.images import detect_image_layout
from reefs.sfm.intrinsics import select_calibration_images
from reefs.splat.validation import _image_files


def _sparse_image(image_id: int, name: str) -> SparseImage:
    return SparseImage(
        image_id=image_id,
        camera_id=1,
        name=name,
        qvec=(1.0, 0.0, 0.0, 0.0),
        tvec=(0.0, 0.0, 0.0),
        center=(0.0, 0.0, 0.0),
        header_line=f"{image_id} 1 0 0 0 0 0 0 1 {name}",
        points_line="",
    )


def test_shared_natural_order_drives_colour_layout_sfm_and_splat_lists(tmp_path: Path) -> None:
    raw = tmp_path / "raw_images"
    raw.mkdir()
    for name in ["img10.jpg", "img1.jpg", "img2.jpg"]:
        Image.new("RGB", (8, 6), color=(10, 20, 30)).save(raw / name)

    sequence = build_image_sequence(raw)
    layout = detect_image_layout(raw)
    selected, _ = select_calibration_images(
        layout=layout,
        selection_start_index=0,
        selection_end_index=3,
    )
    splat_files = _image_files(raw)

    expected = [Path("img1.jpg"), Path("img2.jpg"), Path("img10.jpg")]
    assert sequence.relative_paths == expected
    assert layout.relative_image_paths == expected
    assert selected["single"] == [str(path) for path in expected]
    assert [path.relative_to(raw) for path in splat_files] == expected


def test_patch_export_preserves_natural_selected_image_order(tmp_path: Path) -> None:
    image_root = tmp_path / "images"
    source_sparse = tmp_path / "sparse"
    image_root.mkdir()
    source_sparse.mkdir()
    for name in ["img10.jpg", "img1.jpg", "img2.jpg"]:
        Image.new("RGB", (8, 6), color=(10, 20, 30)).save(image_root / name)
    (source_sparse / "cameras.txt").write_text("1 SIMPLE_PINHOLE 8 6 4 4 3\n", encoding="utf-8")

    selection = PatchSelection(
        bounds=PatchBounds(
            patch_id="p000",
            min_x=0.0,
            max_x=1.0,
            min_y=0.0,
            max_y=1.0,
            min_z=0.0,
            max_z=1.0,
            buffer=0.0,
        ),
        selected_images=[_sparse_image(10, "img10.jpg"), _sparse_image(1, "img1.jpg"), _sparse_image(2, "img2.jpg")],
        local_images=[],
        support_images=[],
        patch_points=[],
        camera_scores=[],
        warnings=[],
        neighbour_bounds=[],
        max_cameras=3,
        external_support_fraction=0.0,
        external_support_allowance=0,
        internal_patch_target=3,
    )

    metadata = export_patch_dataset(
        selection=selection,
        source_sparse=source_sparse,
        image_root=image_root,
        patch_dir=tmp_path / "patch",
        source_run_id="run-1",
        patch_affecting_config={},
    )

    assert metadata["selected_images"] == ["img1.jpg", "img2.jpg", "img10.jpg"]
