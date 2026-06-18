"""Tests for Camera Selection V3."""

from __future__ import annotations

from pathlib import Path

import pytest

from reefs.patches.artefacts import SparseCamera, SparseImage, SparseObservation, SparsePoint, SparseScene
from reefs.patches.bounds import PatchBounds
from reefs.patches.selection import (
    _patch_projection_plane,
    derive_patch_camera_targets,
    discover_one_ring_neighbours,
    select_patch_views,
)


def _image(
    image_id: int,
    name: str,
    center: tuple[float, float, float],
    *,
    point_id: int = 1,
    qvec: tuple[float, float, float, float] = (1, 0, 0, 0),
) -> SparseImage:
    return SparseImage(
        image_id=image_id,
        camera_id=1,
        name=name,
        qvec=qvec,
        tvec=(-center[0], -center[1], -center[2]),
        center=center,
        header_line=f"{image_id} 1 0 0 0 {-center[0]} {-center[1]} {-center[2]} 1 {name}",
        points_line=f"32 24 {point_id}",
        width=64,
        height=48,
        observations=(SparseObservation(32, 24, point_id),),
    )


def _scene(images: list[SparseImage], tracks: dict[int, list[int]] | None = None) -> SparseScene:
    tracks = tracks or {1: [image.image_id for image in images]}
    points = [
        SparsePoint(
            point_id=point_id,
            xyz=(0.0, 0.0, 1.0 + point_id),
            track_image_ids=tuple(image_ids),
            track_point2d_idxs=tuple(0 for _ in image_ids),
            line=" ".join(
                [str(point_id), "0", "0", str(1 + point_id), "255", "255", "255", "0.1"]
                + [token for image_id in image_ids for token in (str(image_id), "0")]
            ),
        )
        for point_id, image_ids in tracks.items()
    ]
    return SparseScene(
        model_dir=Path("."),
        cameras_text="",
        images=images,
        points=points,
        cameras={1: SparseCamera(1, "SIMPLE_PINHOLE", 64, 48, (50.0, 32.0, 24.0))},
    )


def test_derive_patch_camera_targets_reserves_external_allowance() -> None:
    assert derive_patch_camera_targets(400, 0.10) == {
        "max_cameras": 400,
        "external_support_fraction": 0.10,
        "external_support_allowance": 40,
        "internal_patch_target": 360,
    }


def test_useful_internal_cameras_are_not_replaced_by_support() -> None:
    internal = [_image(index, f"internal_{index}.jpg", (0.0, index * 0.1, -5.0)) for index in range(1, 4)]
    support = _image(10, "support.jpg", (2.0, 0.0, -5.0))
    scene = _scene([*internal, support])
    bounds = PatchBounds("p000", -1, 1, -1, 1, -1, 5, 0.1)
    neighbour = PatchBounds("p001", 1, 3, -1, 1, -1, 5, 0.1)

    selection = select_patch_views(scene, bounds, max_cameras=4, external_support_fraction=0.25, all_bounds=[bounds, neighbour])

    assert [score.selection_role for score in selection.camera_scores if score.pool == "internal"] == [
        "kept_internal",
        "kept_internal",
        "kept_internal",
    ]
    assert selection.selected_external_count == 1


def test_unuseful_internal_cameras_are_rejected() -> None:
    useful = _image(1, "useful.jpg", (0.0, 0.0, -5.0))
    unuseful = _image(2, "unuseful.jpg", (0.5, 0.0, -5.0), point_id=99, qvec=(0, 1, 0, 0))
    scene = _scene([useful, unuseful], tracks={1: [1]})
    bounds = PatchBounds("p000", -1, 1, -1, 1, -1, 5, 0.1)

    selection = select_patch_views(scene, bounds, max_cameras=10, external_support_fraction=0.0)

    roles = {score.image_name: score.selection_role for score in selection.camera_scores}
    assert roles["useful.jpg"] == "kept_internal"
    assert roles["unuseful.jpg"] == "rejected_internal"


def test_frustum_footprint_can_make_trackless_internal_camera_useful() -> None:
    trackless = _image(1, "trackless.jpg", (0.0, 0.0, -5.0), point_id=99)
    scene = _scene([trackless], tracks={1: []})
    bounds = PatchBounds("p000", -1, 1, -1, 1, -1, 5, 0.1)

    selection = select_patch_views(scene, bounds, max_cameras=10, external_support_fraction=0.0)

    score = selection.camera_scores[0]
    assert score.visible_patch_track_count == 0
    assert score.footprint_overlap_score > 0
    assert score.target_image_share >= 0.05
    assert score.selection_role == "kept_internal"


def test_frustum_footprint_uses_patch_point_height_not_zero_plane() -> None:
    image = _image(1, "raised_patch.jpg", (0.0, 0.0, 1.8), point_id=1)
    scene = _scene([image], tracks={1: [1]})
    scene.points[0] = SparsePoint(
        point_id=1,
        xyz=(0.0, 0.0, 2.2),
        track_image_ids=(1,),
        track_point2d_idxs=(0,),
        line="1 0 0 2.2 255 255 255 0.1 1 0",
    )
    bounds = PatchBounds("p000", -1, 1, -1, 1, -1, 5, 0.1)

    selection = select_patch_views(scene, bounds, max_cameras=10, external_support_fraction=0.0)

    score = selection.camera_scores[0]
    assert score.footprint_overlap_score > 0
    assert score.target_image_share >= 0.05
    assert score.selection_role == "kept_internal"


def test_patch_projection_plane_follows_local_sparse_point_tilt() -> None:
    points = [
        SparsePoint(
            point_id=index,
            xyz=(x, y, 2.0 + (0.4 * x) - (0.2 * y)),
            track_image_ids=(1,),
            track_point2d_idxs=(0,),
            line="",
        )
        for index, (x, y) in enumerate([(-1, -1), (-1, 1), (1, -1), (1, 1), (0, 0)], start=1)
    ]
    bounds = PatchBounds("p000", -1, 1, -1, 1, -1, 5, 0.1)

    plane = _patch_projection_plane(points, bounds)

    assert plane.method == "least_squares_z_ax_by_c"
    assert plane.z_at(1.0, 0.0) > plane.z_at(-1.0, 0.0)
    assert plane.z_at(0.0, 1.0) < plane.z_at(0.0, -1.0)


def test_internal_only_mode_selects_no_external_support() -> None:
    internal = _image(1, "internal.jpg", (0.0, 0.0, -5.0))
    support = _image(2, "support.jpg", (2.0, 0.0, -5.0))
    scene = _scene([internal, support])
    bounds = PatchBounds("p000", -1, 1, -1, 1, -1, 5, 0.1)
    neighbour = PatchBounds("p001", 1, 3, -1, 1, -1, 5, 0.1)

    selection = select_patch_views(scene, bounds, max_cameras=2, external_support_fraction=0.0, all_bounds=[bounds, neighbour])

    assert selection.selected_external_count == 0
    assert [image.name for image in selection.selected_images] == ["internal.jpg"]


def test_external_candidates_are_limited_to_one_ring_neighbours() -> None:
    internal = _image(1, "internal.jpg", (0.0, 0.0, -5.0))
    neighbour_support = _image(2, "neighbour.jpg", (2.0, 0.0, -5.0))
    distant_support = _image(3, "distant.jpg", (8.0, 0.0, -5.0))
    scene = _scene([internal, neighbour_support, distant_support])
    bounds = PatchBounds("p000", -1, 1, -1, 1, -1, 5, 0.1)
    neighbour = PatchBounds("p001", 1, 3, -1, 1, -1, 5, 0.1)
    distant = PatchBounds("p002", 7, 9, -1, 1, -1, 5, 0.1)

    selection = select_patch_views(
        scene,
        bounds,
        max_cameras=3,
        external_support_fraction=0.5,
        all_bounds=[bounds, neighbour, distant],
    )

    assert [score.image_name for score in selection.camera_scores if score.pool == "external"] == ["neighbour.jpg"]
    assert "distant.jpg" not in [image.name for image in selection.selected_images]


def test_external_support_is_capped_by_allowance() -> None:
    internal = _image(1, "internal.jpg", (0.0, 0.0, -5.0))
    support = [_image(index, f"support_{index}.jpg", (2.0, index, -5.0)) for index in range(2, 5)]
    scene = _scene([internal, *support])
    bounds = PatchBounds("p000", -1, 1, -1, 1, -1, 5, 0.1)
    neighbour = PatchBounds("p001", 1, 5, -1, 5, -1, 5, 0.1)

    selection = select_patch_views(scene, bounds, max_cameras=4, external_support_fraction=0.25, all_bounds=[bounds, neighbour])

    assert selection.external_support_allowance == 1
    assert selection.selected_external_count == 1


def test_external_ranking_uses_azimuth_spread_after_first_pick() -> None:
    internal = _image(1, "internal.jpg", (0.0, 0.0, -5.0))
    same_angle = _image(2, "same_angle.jpg", (2.0, 0.0, -5.0))
    wider_angle = _image(3, "wider_angle.jpg", (0.0, 2.0, -5.0))
    scene = _scene([internal, same_angle, wider_angle])
    bounds = PatchBounds("p000", -1, 1, -1, 1, -1, 5, 0.1)
    n1 = PatchBounds("p001", 1, 3, -1, 1, -1, 5, 0.1)
    n2 = PatchBounds("p002", -1, 1, 1, 3, -1, 5, 0.1)

    selection = select_patch_views(scene, bounds, max_cameras=3, external_support_fraction=0.67, all_bounds=[bounds, n1, n2])

    assert {score.image_name for score in selection.camera_scores if score.selection_role == "selected_external"} == {
        "same_angle.jpg",
        "wider_angle.jpg",
    }


def test_useful_internal_count_exceeding_final_cap_is_a_defect() -> None:
    images = [_image(index, f"internal_{index}.jpg", (0.0, index * 0.1, -5.0)) for index in range(1, 4)]
    scene = _scene(images)
    bounds = PatchBounds("p000", -1, 1, -1, 1, -1, 5, 0.1)

    with pytest.raises(ValueError, match="sizing invariant"):
        select_patch_views(scene, bounds, max_cameras=2)


def test_discover_one_ring_neighbours_excludes_distant_patches() -> None:
    anchor = PatchBounds("p000", 0, 1, 0, 1, 0, 1, 0.1)
    neighbour = PatchBounds("p001", 1, 2, 0, 1, 0, 1, 0.1)
    distant = PatchBounds("p002", 5, 6, 0, 1, 0, 1, 0.1)

    result = discover_one_ring_neighbours([anchor, neighbour, distant], anchor)

    assert [bounds.patch_id for bounds in result] == ["p001"]
