"""Tests for ablation metric helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from reefs.experiments.ablations.metrics import (
    pair_id_to_image_ids,
    parse_lfs_metrics_csv,
    parse_lfs_metrics_rows,
    ply_vertex_count,
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
