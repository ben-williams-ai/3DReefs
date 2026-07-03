"""Tests for ablation metric helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from reefs.experiments.ablations.metrics import (
    _database_keypoint_metrics,
    pair_id_to_image_ids,
    parse_lfs_metrics_csv,
    parse_lfs_metrics_rows,
    ply_vertex_count,
    rank_splat_rows,
)


def _pair_id(image_id1: int, image_id2: int) -> int:
    if image_id1 > image_id2:
        image_id1, image_id2 = image_id2, image_id1
    return image_id1 * 2_147_483_647 + image_id2


def test_colmap_pair_id_round_trip() -> None:
    assert pair_id_to_image_ids(_pair_id(12, 7)) == (7, 12)


def test_ply_vertex_count_reads_header(tmp_path: Path) -> None:
    ply = tmp_path / "splat.ply"
    ply.write_text("ply\nformat ascii 1.0\nelement vertex 42\nend_header\n", encoding="ascii")

    assert ply_vertex_count(ply) == 42


def test_sqlite_available_for_graph_fixture(tmp_path: Path) -> None:
    database = tmp_path / "database.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE images (image_id INTEGER, name TEXT, camera_id INTEGER)")
    assert database.exists()


def test_database_keypoint_metrics_reads_keypoint_rows(tmp_path: Path) -> None:
    database = tmp_path / "database.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE keypoints (image_id INTEGER, rows INTEGER)")
        connection.executemany("INSERT INTO keypoints VALUES (?, ?)", [(1, 100), (2, 300), (3, 500)])

    assert _database_keypoint_metrics(database) == {
        "keypoint_image_count": 3,
        "total_keypoints": 900,
        "min_keypoints_per_image": 100,
        "median_keypoints_per_image": 300,
        "mean_keypoints_per_image": 300,
        "max_keypoints_per_image": 500,
    }


def test_parse_lfs_metrics_csv_uses_latest_eval_row(tmp_path: Path) -> None:
    path = tmp_path / "metrics.csv"
    path.write_text(
        "Iteration,PSNR,SSIM,time_per_image,num_gaussians\n"
        "1000,20.0,0.60,0.1,100\n"
        "2000,21.5,0.66,0.1,120\n",
        encoding="utf-8",
    )

    assert parse_lfs_metrics_csv(path) == {
        "iteration": 2000,
        "psnr": 21.5,
        "ssim": 0.66,
        "time_per_image": 0.1,
        "num_gaussians": 120,
    }


def test_parse_lfs_metrics_csv_preserves_real_lpips(tmp_path: Path) -> None:
    path = tmp_path / "metrics.csv"
    path.write_text(
        "iteration,psnr,ssim,lpips,time_per_image,num_gaussians\n"
        "5000,22.0,0.70,0.31,0.2,1000\n"
        "10000,23.0,0.72,0.28,0.2,1200\n",
        encoding="utf-8",
    )

    assert parse_lfs_metrics_csv(path)["lpips"] == 0.28
    assert [row["iteration"] for row in parse_lfs_metrics_rows(path)] == [5000, 10000]


def test_parse_lfs_metrics_csv_does_not_invent_missing_lpips(tmp_path: Path) -> None:
    path = tmp_path / "metrics.csv"
    path.write_text(
        "iteration,psnr,ssim,time_per_image,num_gaussians\n"
        "5000,22.0,0.70,0.2,1000\n",
        encoding="utf-8",
    )

    assert "lpips" not in parse_lfs_metrics_csv(path)


def test_rank_splat_rows_minimises_lpips_after_ssim_and_psnr() -> None:
    rows = [
        {"job_id": "worse_lpips", "status": "complete", "ssim": "0.70", "psnr": "22.0", "lpips": "0.40"},
        {"job_id": "better_lpips", "status": "complete", "ssim": "0.70", "psnr": "22.0", "lpips": "0.20"},
        {"job_id": "higher_ssim", "status": "complete", "ssim": "0.71", "psnr": "21.0", "lpips": "0.90"},
    ]

    assert [row["job_id"] for row in rank_splat_rows(rows)] == [
        "higher_ssim",
        "better_lpips",
        "worse_lpips",
    ]


def test_rank_splat_rows_keeps_missing_lpips_behind_real_lpips_when_other_metrics_match() -> None:
    rows = [
        {"job_id": "missing_lpips", "status": "complete", "ssim": "0.70", "psnr": "22.0", "lpips": ""},
        {"job_id": "real_lpips", "status": "complete", "ssim": "0.70", "psnr": "22.0", "lpips": "0.35"},
    ]

    assert [row["job_id"] for row in rank_splat_rows(rows)] == ["real_lpips", "missing_lpips"]
