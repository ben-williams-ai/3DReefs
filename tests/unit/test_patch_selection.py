"""Tests for Camera Selection V2."""

from __future__ import annotations

from reefs.patches.artefacts import SparseImage, SparseObservation, SparsePoint, SparseScene
from reefs.patches.bounds import PatchBounds
from reefs.patches.selection import (
    SELECTOR_NAME,
    SELECTOR_VERSION,
    CameraSelectionScore,
    _select_greedily,
    balanced_sector_selection,
    discover_one_ring_neighbours,
    select_patch_views,
    sort_scores,
)
from reefs.patches.visibility import TargetSample
from tests.fixtures.patch_selection import bounds as fixture_bounds
from tests.fixtures.patch_selection import image as fixture_image
from tests.fixtures.patch_selection import point as fixture_point
from tests.fixtures.patch_selection import scene as fixture_scene


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


def _score(
    image_id: int,
    name: str,
    *,
    sample_ids: frozenset[int],
    track: float = 0.0,
    geometry: float = 0.0,
    target_share: float = 0.1,
    pool: str = "internal",
    sector: int = 0,
) -> CameraSelectionScore:
    return CameraSelectionScore(
        image_id=image_id,
        image_name=name,
        source_patch="p000",
        pool=pool,
        azimuth_sector=sector,
        azimuth_degrees=float(sector * 45),
        visible_patch_points=1 if track else 0,
        projected_target_area_ratio=target_share,
        median_visible_depth=1,
        camera_x=0,
        camera_y=0,
        camera_z=0,
        matched_track_score=track,
        geometric_visibility_score=geometry,
        target_image_share=target_share,
        target_sample_ids=sample_ids,
    )


def test_select_patch_views_uses_external_camera_with_direct_track_evidence(tmp_path) -> None:
    internal = _image(1, "internal.jpg", (0, 0, 0))
    external = _image(2, "external.jpg", (2, 0, 0))
    scene = SparseScene(
        model_dir=tmp_path,
        cameras_text="",
        images=[internal, external],
        points=[SparsePoint(point_id=1, xyz=(0, 0, 1), track_image_ids=(1, 2), line="1 0 0 1 255 255 255 0.1 1 0 2 0")],
    )
    bounds = PatchBounds("p000", -1, 1, -1, 1, -1, 2, 0.1)
    neighbour = PatchBounds("p001", 1, 3, -1, 1, -1, 2, 0.1)

    selection = select_patch_views(scene, bounds, max_cameras=2, all_bounds=[bounds, neighbour])

    assert [image.name for image in selection.selected_images] == ["internal.jpg", "external.jpg"]
    assert selection.as_dict()["selected_external_count"] == 1


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


def test_sort_scores_does_not_privilege_boundary_terms() -> None:
    track = _score(1, "track.jpg", sample_ids=frozenset({1}), track=0.8, geometry=0.1, target_share=0.1)
    geometry = _score(2, "geometry.jpg", sample_ids=frozenset({1, 2}), track=0.0, geometry=0.9, target_share=0.2)

    assert sort_scores([track, geometry])[0].image_name == "geometry.jpg"


def test_balanced_sector_selection_spreads_populated_sectors() -> None:
    scores = [_score(index, f"image_{index}.jpg", sample_ids=frozenset({index}), geometry=1.0, sector=sector) for index, sector in enumerate([0, 0, 0, 1, 1, 2], start=1)]

    selected = balanced_sector_selection(scores, 3)

    assert {score.azimuth_sector for score in selected} == {0, 1, 2}


def test_discover_one_ring_neighbours_excludes_distant_patches() -> None:
    anchor = PatchBounds("p000", 0, 1, 0, 1, 0, 1, 0.1)
    neighbour = PatchBounds("p001", 1, 2, 0, 1, 0, 1, 0.1)
    distant = PatchBounds("p002", 5, 6, 0, 1, 0, 1, 0.1)

    result = discover_one_ring_neighbours([anchor, neighbour, distant], anchor)

    assert [bounds.patch_id for bounds in result] == ["p001"]


def test_camera_selection_v2_records_selector_metadata(tmp_path) -> None:
    internal = fixture_image(1, "internal.jpg", center=(0, 0, 0))
    sparse_scene = fixture_scene(tmp_path, [internal], [fixture_point(1, (0, 0, 4), (1,))])

    selection = select_patch_views(sparse_scene, fixture_bounds(), max_cameras=10)

    assert selection.selector["name"] == SELECTOR_NAME
    assert selection.selector["version"] == SELECTOR_VERSION
    assert selection.selector["coverage"]["footprint"] > 0
    assert selection.camera_scores[0].matched_track_score > 0


def test_selector_keeps_useful_candidates_until_camera_cap() -> None:
    target_samples = [TargetSample(sample_id=1, xyz=(0, 0, 1), cell_id="0:0:0")]

    selected = _select_greedily(
        [
            _score(1, "first.jpg", sample_ids=frozenset({1}), track=1.0, target_share=0.5),
            _score(2, "low_gain_a.jpg", sample_ids=frozenset(), track=0.01, target_share=0.0),
            _score(3, "low_gain_b.jpg", sample_ids=frozenset(), track=0.01, target_share=0.0),
        ],
        max_cameras=3,
        target_samples=target_samples,
    )

    assert [item.image_name for item in selected] == ["first.jpg", "low_gain_a.jpg", "low_gain_b.jpg"]


def test_either_signal_fusion_can_select_projection_only_camera(tmp_path) -> None:
    track_camera = fixture_image(1, "track.jpg", center=(0, 0, 0))
    projection_camera = fixture_image(2, "projection.jpg", center=(0.4, 0, 0))
    sparse_scene = fixture_scene(tmp_path, [track_camera, projection_camera], [fixture_point(1, (0, 0, 4), (1,))])

    selection = select_patch_views(sparse_scene, fixture_bounds(), max_cameras=2)

    assert {image.name for image in selection.selected_images} == {"track.jpg", "projection.jpg"}
    projection_score = next(score for score in selection.camera_scores if score.image_name == "projection.jpg")
    assert projection_score.matched_track_score == 0
    assert projection_score.geometric_visibility_score > 0


def test_internal_camera_pointing_away_is_disadvantaged(tmp_path) -> None:
    away_internal = fixture_image(1, "away_internal.jpg", center=(0, 0, 0), qvec=(0, 0, 1, 0))
    useful_external = fixture_image(2, "useful_external.jpg", center=(1.5, 0, 0))
    sparse_scene = fixture_scene(tmp_path, [away_internal, useful_external], [fixture_point(1, (0, 0, 4), (2,))])
    patch_bounds = fixture_bounds()
    neighbour = PatchBounds("p001", 1, 3, -1, 1, -1, 6, 0.1)

    selection = select_patch_views(sparse_scene, patch_bounds, max_cameras=1, all_bounds=[patch_bounds, neighbour])

    assert [image.name for image in selection.selected_images] == ["useful_external.jpg"]
    away_score = next(score for score in selection.camera_scores if score.image_name == "away_internal.jpg")
    assert away_score.rejection_reason == "no_target_evidence"


def test_full_footprint_visibility_preserves_sparse_hole_camera(tmp_path) -> None:
    left = fixture_image(1, "left.jpg", center=(-0.8, 0, 0))
    right = fixture_image(2, "right_sparse_hole.jpg", center=(0.8, 0, 0))
    sparse_scene = fixture_scene(tmp_path, [left, right], [fixture_point(1, (-0.8, 0, 4), (1,))])

    selection = select_patch_views(sparse_scene, fixture_bounds(), max_cameras=2)

    assert {image.name for image in selection.selected_images} == {"left.jpg", "right_sparse_hole.jpg"}
    right_score = next(score for score in selection.camera_scores if score.image_name == "right_sparse_hole.jpg")
    assert right_score.geometric_visibility_score > 0


def test_dense_cluster_does_not_block_coverage_camera(tmp_path) -> None:
    dense = fixture_image(1, "dense_cluster.jpg", center=(-0.8, 0, 0))
    sparse = fixture_image(2, "sparse_side.jpg", center=(0.8, 0, 0))
    points = [fixture_point(point_id, (-0.8, 0, 4), (1,)) for point_id in range(1, 8)]
    points.append(fixture_point(20, (0.8, 0, 4), (2,)))
    sparse_scene = fixture_scene(tmp_path, [dense, sparse], points)

    selection = select_patch_views(sparse_scene, fixture_bounds(), max_cameras=2)

    assert {image.name for image in selection.selected_images} == {"dense_cluster.jpg", "sparse_side.jpg"}
