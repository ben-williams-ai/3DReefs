"""Tests for COLMAP-safe SfM image staging."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from reefs.preflight.images import ImageLayout
from reefs.sfm.intrinsics import CameraIntrinsics
from reefs.sfm.pipeline import _seed_database_camera_intrinsics, _stage_colmap_safe_images, _staged_camera_group_aliases


def test_stage_colmap_safe_images_removes_whitespace_and_preserves_order(tmp_path: Path) -> None:
    source = tmp_path / "raw"
    target = tmp_path / "staged"
    first = source / "Cam Left" / "Frame One (1).JPG"
    second = source / "Cam Left" / "Frame Two (2).JPG"
    first.parent.mkdir(parents=True)
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    layout = ImageLayout(
        kind="multi",
        image_paths=[Path("Cam Left/Frame One (1).JPG"), Path("Cam Left/Frame Two (2).JPG")],
        camera_dirs=["Cam Left"],
    )

    staged = _stage_colmap_safe_images(source_root=source, layout=layout, target_root=target)

    assert len(staged.relative_image_paths) == 2
    assert staged.relative_image_paths[0].parent.name.startswith("cam_left_")
    assert staged.relative_image_paths[0].name.startswith("img_000001_")
    assert staged.relative_image_paths[1].name.startswith("img_000002_")
    assert all(" " not in path.as_posix() for path in staged.relative_image_paths)
    assert not (target / staged.relative_image_paths[0]).is_symlink()
    assert not (target / staged.relative_image_paths[1]).is_symlink()
    assert (target / staged.relative_image_paths[0]).read_bytes() == first.read_bytes()
    assert (target / staged.relative_image_paths[1]).read_bytes() == second.read_bytes()


def test_stage_colmap_safe_images_keeps_sanitised_camera_names_distinct(tmp_path: Path) -> None:
    source = tmp_path / "raw"
    target = tmp_path / "staged"
    first = source / "Cam 1" / "a.jpg"
    second = source / "cam-1" / "a.jpg"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    layout = ImageLayout(
        kind="multi",
        image_paths=[Path("Cam 1/a.jpg"), Path("cam-1/a.jpg")],
        camera_dirs=["Cam 1", "cam-1"],
    )

    staged = _stage_colmap_safe_images(source_root=source, layout=layout, target_root=target)

    assert staged.relative_image_paths[0].parent != staged.relative_image_paths[1].parent
    assert not (target / staged.relative_image_paths[0]).is_symlink()
    assert not (target / staged.relative_image_paths[1]).is_symlink()
    assert (target / staged.relative_image_paths[0]).read_bytes() == first.read_bytes()
    assert (target / staged.relative_image_paths[1]).read_bytes() == second.read_bytes()


def test_seed_intrinsics_maps_staged_camera_names_to_original_groups(tmp_path: Path) -> None:
    database = tmp_path / "database.db"
    layout = ImageLayout(
        kind="multi",
        image_paths=[Path("Cam 1/a.jpg"), Path("Cam 2/a.jpg")],
        camera_dirs=["Cam 1", "Cam 2"],
    )
    for relative_path in layout.relative_image_paths:
        image_path = tmp_path / relative_path
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"image")
    staged = _stage_colmap_safe_images(source_root=tmp_path, layout=layout, target_root=tmp_path / "staged")

    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE cameras (camera_id INTEGER PRIMARY KEY, model INTEGER, width INTEGER, height INTEGER, params BLOB, prior_focal_length INTEGER)"
        )
        connection.execute("CREATE TABLE images (image_id INTEGER PRIMARY KEY, name TEXT, camera_id INTEGER)")
        connection.execute("INSERT INTO cameras VALUES (1, 0, 1, 1, ?, 0)", (sqlite3.Binary(b""),))
        connection.execute("INSERT INTO cameras VALUES (2, 0, 1, 1, ?, 0)", (sqlite3.Binary(b""),))
        for image_id, staged_path in enumerate(staged.relative_image_paths, start=1):
            connection.execute(
                "INSERT INTO images VALUES (?, ?, ?)",
                (image_id, staged_path.as_posix(), image_id),
            )
        connection.commit()

    seeded = _seed_database_camera_intrinsics(
        database=database,
        intrinsics_by_group={
            "Cam 1": CameraIntrinsics(1, "OPENCV", 5568, 4872, (1.0, 2.0, 3.0, 4.0, 0.0, 0.0, 0.0, 0.0)),
            "Cam 2": CameraIntrinsics(2, "OPENCV", 5568, 4872, (5.0, 6.0, 7.0, 8.0, 0.0, 0.0, 0.0, 0.0)),
        },
        camera_group_aliases=_staged_camera_group_aliases(layout),
    )

    assert sorted(seeded) == ["Cam 1", "Cam 2"]
    with sqlite3.connect(database) as connection:
        rows = connection.execute("SELECT camera_id, model, width, height, prior_focal_length FROM cameras").fetchall()
    assert rows == [(1, 4, 5568, 4872, 1), (2, 4, 5568, 4872, 1)]
