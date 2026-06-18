"""Tests for view-based patch selection."""

from __future__ import annotations

from reefs.patches.artefacts import SparseImage, SparseObservation, SparsePoint, SparseScene
from reefs.patches.bounds import PatchBounds
from reefs.patches.selection import CameraSelectionScore, balanced_sector_selection, discover_one_ring_neighbours, select_patch_views, sort_scores


def _image(image_id: int, name: str, center: tuple[float, float, float]) -> SparseImage:
    return SparseImage(
        image_id=image_id,
        camera_id=1,
        name=name,
        qvec=(1, 0, 0, 0),
        tvec=(-center[0], -center[1], -center[2]),
        center=center,
        header_line=f"{image_id} 1 0 0 0 {-center[0]} {-center[1]} {-center[2]} 1 {name}",
        points_line="32 24 1",
        width=64,
        height=48,
        observations=(SparseObservation(32, 24, 1),),
    )


def test_select_patch_views_uses_sparse_support_not_only_local_cameras(tmp_path) -> None:
    local = _image(1, "local.jpg", (0, 0, 0))
    support = _image(2, "support.jpg", (2, 0, 0))
    scene = SparseScene(
        model_dir=tmp_path,
        cameras_text="",
        images=[local, support],
        points=[SparsePoint(point_id=1, xyz=(0, 0, 1), track_image_ids=(1, 2), line="1 0 0 1 255 255 255 0.1 1 0 2 0")],
    )
    bounds = PatchBounds("p000", -1, 1, -1, 1, -1, 2, 0.1)
    neighbour = PatchBounds("p001", 1, 3, -1, 1, -1, 2, 0.1)

    selection = select_patch_views(scene, bounds, max_cameras=2, all_bounds=[bounds, neighbour])

    assert [image.name for image in selection.selected_images] == ["local.jpg", "support.jpg"]
    assert selection.patch_points[0].point_id == 1
    assert selection.as_dict()["selected_support_count"] == 1


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


def test_patch_bounds_detect_boundary_band() -> None:
    bounds = PatchBounds("p000", 0, 10, 0, 10, -1, 1, 1)

    assert bounds.is_boundary_xy(0.5, 5)
    assert not bounds.is_boundary_xy(5, 5)
    assert not bounds.is_boundary_xy(11, 5)


def test_ranking_prefers_boundary_coverage_before_raw_visibility() -> None:
    boundary = CameraSelectionScore(
        image_id=1,
        image_name="boundary.jpg",
        source_patch="p000",
        pool="local",
        azimuth_sector=0,
        azimuth_degrees=0,
        core_visible_points=10,
        boundary_visible_points=5,
        interior_visible_points=5,
        projected_core_area_ratio=0.1,
        projected_boundary_area_ratio=0.1,
        projected_interior_area_ratio=0.1,
        median_visible_depth=5,
        camera_x=0,
        camera_y=0,
        camera_z=0,
    )
    raw = CameraSelectionScore(
        image_id=2,
        image_name="raw.jpg",
        source_patch="p000",
        pool="local",
        azimuth_sector=0,
        azimuth_degrees=0,
        core_visible_points=100,
        boundary_visible_points=1,
        interior_visible_points=99,
        projected_core_area_ratio=0.9,
        projected_boundary_area_ratio=0.01,
        projected_interior_area_ratio=0.9,
        median_visible_depth=1,
        camera_x=0,
        camera_y=0,
        camera_z=0,
    )

    assert sort_scores([raw, boundary])[0].image_name == "boundary.jpg"


def test_balanced_sector_selection_spreads_populated_sectors() -> None:
    scores = [
        CameraSelectionScore(
            image_id=index,
            image_name=f"image_{index}.jpg",
            source_patch="p000",
            pool="local",
            azimuth_sector=sector,
            azimuth_degrees=float(sector * 45),
            core_visible_points=10,
            boundary_visible_points=10,
            interior_visible_points=0,
            projected_core_area_ratio=0.1,
            projected_boundary_area_ratio=0.1,
            projected_interior_area_ratio=0.0,
            median_visible_depth=1,
            camera_x=0,
            camera_y=0,
            camera_z=0,
        )
        for index, sector in enumerate([0, 0, 0, 1, 1, 2], start=1)
    ]

    selected = balanced_sector_selection(scores, 3)

    assert {score.azimuth_sector for score in selected} == {0, 1, 2}


def test_discover_one_ring_neighbours_excludes_distant_patches() -> None:
    anchor = PatchBounds("p000", 0, 1, 0, 1, 0, 1, 0.1)
    neighbour = PatchBounds("p001", 1, 2, 0, 1, 0, 1, 0.1)
    distant = PatchBounds("p002", 5, 6, 0, 1, 0, 1, 0.1)

    result = discover_one_ring_neighbours([anchor, neighbour, distant], anchor)

    assert [bounds.patch_id for bounds in result] == ["p001"]
