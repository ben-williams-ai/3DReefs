"""Tests for view-based patch selection."""

from __future__ import annotations

from reefs.patches.artefacts import SparseImage, SparsePoint, SparseScene
from reefs.patches.bounds import PatchBounds
from reefs.patches.selection import select_patch_views


def _image(image_id: int, name: str, center: tuple[float, float, float]) -> SparseImage:
    return SparseImage(
        image_id=image_id,
        camera_id=1,
        name=name,
        qvec=(1, 0, 0, 0),
        tvec=(-center[0], -center[1], -center[2]),
        center=center,
        header_line=f"{image_id} 1 0 0 0 {-center[0]} {-center[1]} {-center[2]} 1 {name}",
        points_line="",
    )


def test_select_patch_views_uses_sparse_support_not_only_local_cameras(tmp_path) -> None:
    local = _image(1, "local.jpg", (0, 0, 0))
    support = _image(2, "support.jpg", (10, 0, 0))
    scene = SparseScene(
        model_dir=tmp_path,
        cameras_text="",
        images=[local, support],
        points=[SparsePoint(point_id=1, xyz=(0, 0, 1), track_image_ids=(1, 2), line="1 0 0 1 255 255 255 0.1 1 0 2 0")],
    )
    bounds = PatchBounds("p000", -1, 1, -1, 1, -1, 2, 0.1)

    selection = select_patch_views(scene, bounds, max_cameras=2)

    assert [image.name for image in selection.selected_images] == ["local.jpg", "support.jpg"]
    assert selection.patch_points[0].point_id == 1


def test_select_patch_views_caps_selected_cameras(tmp_path) -> None:
    images = [_image(index, f"image_{index}.jpg", (0, index, 0)) for index in range(1, 4)]
    scene = SparseScene(
        model_dir=tmp_path,
        cameras_text="",
        images=images,
        points=[
            SparsePoint(
                point_id=1,
                xyz=(0, 0, 0),
                track_image_ids=(1, 2, 3),
                line="1 0 0 0 255 255 255 0.1 1 0 2 0 3 0",
            )
        ],
    )
    bounds = PatchBounds("p000", -1, 1, -1, 4, -1, 1, 0.1)

    selection = select_patch_views(scene, bounds, max_cameras=2)

    assert len(selection.selected_images) == 2
    assert "Selection capped" in selection.warnings[0]
