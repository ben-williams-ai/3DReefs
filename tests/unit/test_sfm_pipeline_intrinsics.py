"""Tests for applying precalculated intrinsics to COLMAP databases."""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

from reefs.sfm.intrinsics import CameraIntrinsics
from reefs.sfm.pipeline import (
    _prepare_dense_output_directories,
    _prepare_intrinsics_subset,
    _reindex_colmap_database_images,
    _seed_database_camera_intrinsics,
)


def _create_colmap_database(path: Path, image_rows: list[tuple[str, int]]) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE cameras (
                camera_id INTEGER PRIMARY KEY,
                model INTEGER NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                params BLOB NOT NULL,
                prior_focal_length INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE images (
                image_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                camera_id INTEGER NOT NULL
            )
            """
        )
        connection.execute("CREATE TABLE keypoints (image_id INTEGER PRIMARY KEY, rows INTEGER)")
        connection.execute("CREATE TABLE descriptors (image_id INTEGER PRIMARY KEY, rows INTEGER)")
        connection.execute("CREATE TABLE frame_data (frame_id INTEGER, data_id INTEGER, sensor_id INTEGER, sensor_type INTEGER)")
        connection.execute("CREATE TABLE pose_priors (pose_prior_id INTEGER PRIMARY KEY, corr_data_id INTEGER)")
        connection.execute("CREATE TABLE matches (pair_id INTEGER PRIMARY KEY, rows INTEGER)")
        connection.execute("CREATE TABLE two_view_geometries (pair_id INTEGER PRIMARY KEY, rows INTEGER)")
        for camera_id in sorted({camera_id for _, camera_id in image_rows}):
            connection.execute(
                "INSERT INTO cameras VALUES (?, ?, ?, ?, ?, ?)",
                (camera_id, 4, 1, 1, sqlite3.Binary(struct.pack("<8d", *([0.0] * 8))), 0),
            )
        for image_id, (name, camera_id) in enumerate(image_rows, start=1):
            connection.execute("INSERT INTO images VALUES (?, ?, ?)", (image_id, name, camera_id))
            connection.execute("INSERT INTO keypoints VALUES (?, ?)", (image_id, image_id * 10))
            connection.execute("INSERT INTO descriptors VALUES (?, ?)", (image_id, image_id * 100))
            connection.execute("INSERT INTO frame_data VALUES (?, ?, ?, ?)", (image_id, image_id, camera_id, 0))
            connection.execute("INSERT INTO pose_priors VALUES (?, ?)", (image_id, image_id))
        connection.commit()


def _params_for_camera(path: Path, camera_id: int) -> tuple[float, ...]:
    with sqlite3.connect(path) as connection:
        blob = connection.execute(
            "SELECT params FROM cameras WHERE camera_id = ?",
            (camera_id,),
        ).fetchone()[0]
    return struct.unpack("<8d", blob)


def test_seed_database_camera_intrinsics_writes_distinct_params(tmp_path: Path) -> None:
    database = tmp_path / "database.db"
    _create_colmap_database(database, [("cam1/a.jpg", 11), ("cam2/a.jpg", 22)])

    seeded = _seed_database_camera_intrinsics(
        database=database,
        intrinsics_by_group={
            "cam1": CameraIntrinsics(1, "OPENCV", 64, 48, (1, 2, 3, 4, 0.1, 0.2, 0.3, 0.4)),
            "cam2": CameraIntrinsics(2, "OPENCV", 64, 48, (5, 6, 7, 8, 0.5, 0.6, 0.7, 0.8)),
        },
    )

    assert seeded["cam1"]["full_camera_id"] == 11
    assert seeded["cam2"]["full_camera_id"] == 22
    assert _params_for_camera(database, 11) == (1, 2, 3, 4, 0.1, 0.2, 0.3, 0.4)
    assert _params_for_camera(database, 22) == (5, 6, 7, 8, 0.5, 0.6, 0.7, 0.8)


def test_reindex_colmap_database_images_updates_pre_match_tables(tmp_path: Path) -> None:
    database = tmp_path / "database.db"
    _create_colmap_database(
        database,
        [("cam1/DSC00001.jpg", 11), ("cam1/DSC09999.jpg", 11), ("cam1/DSC00002.jpg", 11)],
    )

    image_ids = _reindex_colmap_database_images(
        database=database,
        ordered_image_names=["cam1/DSC09999.jpg", "cam1/DSC00001.jpg", "cam1/DSC00002.jpg"],
    )

    assert image_ids == {
        "cam1/DSC09999.jpg": 1,
        "cam1/DSC00001.jpg": 2,
        "cam1/DSC00002.jpg": 3,
    }
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT image_id, name FROM images ORDER BY image_id").fetchall() == [
            (1, "cam1/DSC09999.jpg"),
            (2, "cam1/DSC00001.jpg"),
            (3, "cam1/DSC00002.jpg"),
        ]
        assert connection.execute("SELECT image_id, rows FROM keypoints ORDER BY image_id").fetchall() == [
            (1, 20),
            (2, 10),
            (3, 30),
        ]
        assert connection.execute("SELECT image_id, rows FROM descriptors ORDER BY image_id").fetchall() == [
            (1, 200),
            (2, 100),
            (3, 300),
        ]
        assert connection.execute("SELECT data_id FROM frame_data ORDER BY data_id").fetchall() == [(1,), (2,), (3,)]
        assert connection.execute("SELECT corr_data_id FROM pose_priors ORDER BY corr_data_id").fetchall() == [
            (1,),
            (2,),
            (3,),
        ]


def test_reindex_colmap_database_images_refuses_populated_matches(tmp_path: Path) -> None:
    database = tmp_path / "database.db"
    _create_colmap_database(database, [("a.jpg", 1), ("b.jpg", 1)])
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO two_view_geometries VALUES (?, ?)", (1, 1))
        connection.commit()

    try:
        _reindex_colmap_database_images(database=database, ordered_image_names=["b.jpg", "a.jpg"])
    except ValueError as exc:
        assert "after matching" in str(exc)
    else:
        raise AssertionError("Expected populated matching tables to be rejected")


def test_prepare_intrinsics_subset_copies_images(tmp_path: Path) -> None:
    source_root = tmp_path / "raw_images"
    source_image = source_root / "cam1" / "a.jpg"
    source_image.parent.mkdir(parents=True)
    source_image.write_bytes(b"image")

    target_root = tmp_path / "subset"

    _prepare_intrinsics_subset(
        source_root=source_root,
        selected_images={"cam1": ["cam1/a.jpg"]},
        target_root=target_root,
    )

    target_image = target_root / "cam1" / "a.jpg"
    assert target_image.read_bytes() == b"image"
    assert not target_image.is_symlink()


def test_seed_database_camera_intrinsics_fails_when_group_is_missing(tmp_path: Path) -> None:
    database = tmp_path / "database.db"
    _create_colmap_database(database, [("cam1/a.jpg", 11)])

    try:
        _seed_database_camera_intrinsics(
            database=database,
            intrinsics_by_group={
                "cam1": CameraIntrinsics(1, "OPENCV", 64, 48, (1, 2, 3, 4, 0.1, 0.2, 0.3, 0.4)),
                "cam2": CameraIntrinsics(2, "OPENCV", 64, 48, (5, 6, 7, 8, 0.5, 0.6, 0.7, 0.8)),
            },
        )
    except ValueError as exc:
        assert "do not match" in str(exc)
    else:
        raise AssertionError("Expected missing camera group to be rejected")


def test_seed_database_camera_intrinsics_fails_when_folder_has_multiple_camera_ids(
    tmp_path: Path,
) -> None:
    database = tmp_path / "database.db"
    _create_colmap_database(database, [("cam1/a.jpg", 11), ("cam1/b.jpg", 22)])

    try:
        _seed_database_camera_intrinsics(
            database=database,
            intrinsics_by_group={
                "cam1": CameraIntrinsics(1, "OPENCV", 64, 48, (1, 2, 3, 4, 0.1, 0.2, 0.3, 0.4)),
            },
        )
    except ValueError as exc:
        assert "maps to multiple full-run COLMAP camera IDs" in str(exc)
    else:
        raise AssertionError("Expected duplicate full-run camera IDs to be rejected")


def test_prepare_dense_output_directories_for_nested_image_names(tmp_path: Path) -> None:
    workspace = tmp_path / "undistorted"
    (workspace / "images" / "cam1").mkdir(parents=True)
    (workspace / "images" / "cam1" / "a.jpg").write_bytes(b"image")

    _prepare_dense_output_directories(workspace)

    assert (workspace / "stereo" / "depth_maps" / "cam1").is_dir()
    assert (workspace / "stereo" / "normal_maps" / "cam1").is_dir()
    assert (workspace / "stereo" / "consistency_graphs" / "cam1").is_dir()
