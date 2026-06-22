"""Tests for applying precalculated intrinsics to COLMAP databases."""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

from reefs.sfm.intrinsics import CameraIntrinsics
from reefs.sfm.pipeline import _seed_database_camera_intrinsics


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
        for camera_id in sorted({camera_id for _, camera_id in image_rows}):
            connection.execute(
                "INSERT INTO cameras VALUES (?, ?, ?, ?, ?, ?)",
                (camera_id, 4, 1, 1, sqlite3.Binary(struct.pack("<8d", *([0.0] * 8))), 0),
            )
        for image_id, (name, camera_id) in enumerate(image_rows, start=1):
            connection.execute("INSERT INTO images VALUES (?, ?, ?)", (image_id, name, camera_id))
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
