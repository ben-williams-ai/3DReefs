"""Tests for patch target visibility helpers."""

from __future__ import annotations

from reefs.patches.bounds import PatchBounds
from reefs.patches.visibility import build_target_samples, parse_camera_intrinsics, project_world_point, sparse_point_density_weights
from tests.fixtures.patch_selection import bounds, image, point, scene


def test_parse_camera_intrinsics_and_project_point(tmp_path) -> None:
    sparse_scene = scene(tmp_path, [image(1, "image.jpg", center=(0, 0, 0))], [])
    intrinsics = parse_camera_intrinsics(sparse_scene.cameras_text)

    projected = project_world_point(sparse_scene.images[0], intrinsics[1], (0, 0, 4))

    assert projected is not None
    assert projected[:2] == (32, 24)
    assert projected[2] == 4


def test_build_target_samples_labels_body_and_boundary(tmp_path) -> None:
    sparse_scene = scene(tmp_path, [image(index, f"image_{index}.jpg", center=(0, 0, 0)) for index in range(1, 101)], [])

    samples = build_target_samples(sparse_scene, PatchBounds("p000", -1, 1, -1, 1, -1, 6, 0.3), [])

    assert samples
    assert {sample.role for sample in samples} == {"body", "boundary"}
    assert all(sample.cell_id for sample in samples)


def test_target_samples_use_scene_scaled_aspect_grid(tmp_path) -> None:
    images = [image(index, f"image_{index}.jpg", center=(0, 0, 0)) for index in range(1, 101)]
    sparse_scene = scene(tmp_path, images, [])
    wide = PatchBounds("p000", 0, 4, 0, 1, -1, 1, 0.1)
    narrow = PatchBounds("p001", 4, 5, 0, 1, -1, 1, 0.1)

    samples = build_target_samples(sparse_scene, wide, [], all_bounds=[wide, narrow])
    cells = {sample.cell_id.rsplit(":", 1)[0] for sample in samples}
    x_indices = {cell.split(":")[0] for cell in cells}
    y_indices = {cell.split(":")[1] for cell in cells}

    assert len(cells) >= 16
    assert len(x_indices) > len(y_indices)


def test_target_samples_use_cell_specific_heights(tmp_path) -> None:
    sparse_scene = scene(
        tmp_path,
        [image(index, f"image_{index}.jpg", center=(0, 0, 0)) for index in range(1, 101)],
        [
            point(1, (-0.8, 0, 1), (1,)),
            point(2, (-0.7, 0, 1.1), (1,)),
            point(3, (-0.6, 0, 1.2), (1,)),
            point(4, (0.8, 0, 0), (1,)),
            point(5, (0.8, 0, 1), (1,)),
            point(6, (0.8, 0, 2), (1,)),
            point(7, (0.8, 0, 3), (1,)),
            point(8, (0.8, 0, 4), (1,)),
            point(9, (0.8, 0, 5), (1,)),
            point(10, (0.8, 0, 6), (1,)),
            point(11, (0.8, 0, 7), (1,)),
        ],
    )

    samples = build_target_samples(sparse_scene, bounds(), sparse_scene.points)
    z_by_xy = {}
    for sample in samples:
        z_by_xy.setdefault(sample.cell_id.rsplit(":", 1)[0], set()).add(sample.xyz[2])

    assert max(len(values) for values in z_by_xy.values()) > 1


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
