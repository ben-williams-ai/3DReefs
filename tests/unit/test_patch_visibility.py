"""Tests for patch target visibility helpers."""

from __future__ import annotations

from reefs.patches.visibility import (
    build_target_samples,
    parse_camera_intrinsics,
    project_world_point,
    sparse_point_density_weights,
)
from tests.fixtures.patch_selection import bounds, image, point, scene


def test_parse_camera_intrinsics_and_project_point(tmp_path) -> None:
    sparse_scene = scene(tmp_path, [image(1, "image.jpg", center=(0, 0, 0))], [])
    intrinsics = parse_camera_intrinsics(sparse_scene.cameras_text)

    projected = project_world_point(sparse_scene.images[0], intrinsics[1], (0, 0, 4))

    assert projected is not None
    assert projected[:2] == (32, 24)
    assert projected[2] == 4


def test_build_target_samples_labels_body_and_boundary(tmp_path) -> None:
    sparse_scene = scene(tmp_path, [image(1, "image.jpg", center=(0, 0, 0))], [])

    samples = build_target_samples(sparse_scene, bounds(), [], grid_size=12)

    assert samples
    assert {sample.role for sample in samples} == {"body", "boundary"}
    assert all(sample.cell_id for sample in samples)


def test_sparse_point_density_weights_downweight_dense_cells(tmp_path) -> None:
    patch_bounds = bounds()
    points = [
        point(1, (-0.9, -0.9, 4), (1,)),
        point(2, (-0.8, -0.8, 4), (1,)),
        point(3, (0.8, 0.8, 4), (1,)),
    ]

    weights = sparse_point_density_weights(points, patch_bounds, grid_size=2)

    assert weights[1] == weights[2]
    assert weights[3] > weights[1]
