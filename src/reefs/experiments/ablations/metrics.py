"""Metric extraction for ablation sweeps."""

from __future__ import annotations

import csv
import math
import re
import sqlite3
import statistics
import subprocess
from collections import defaultdict, deque
from pathlib import Path


COLMAP_PAIR_ID_BASE = 2_147_483_647


def parse_lfs_metrics_csv(path: Path) -> dict[str, float | int]:
    """Return the final LFS eval metrics row."""
    if not path.exists():
        return {}
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            normalised = {key.strip().lower(): value for key, value in row.items() if key is not None}
            if normalised.get("psnr") and normalised.get("ssim"):
                rows.append(normalised)
    if not rows:
        return {}
    row = rows[-1]
    return {
        "iteration": int(float(row["iteration"])),
        "psnr": float(row["psnr"]),
        "ssim": float(row["ssim"]),
        "time_per_image": float(row.get("time_per_image") or 0.0),
        "num_gaussians": int(float(row.get("num_gaussians") or 0)),
    }


def ply_vertex_count(path: Path) -> int | None:
    """Return the vertex count from a PLY header."""
    if not path.exists():
        return None
    with path.open("rb") as handle:
        for raw in handle:
            line = raw.decode("ascii", errors="ignore").strip()
            if line.startswith("element vertex "):
                parts = line.split()
                if len(parts) == 3 and parts[2].isdigit():
                    return int(parts[2])
            if line == "end_header":
                return None
    return None


def file_size(path: Path) -> int | None:
    """Return file size in bytes when the file exists."""
    return path.stat().st_size if path.exists() else None


def sfm_metrics(*, colmap_bin: str, run_dir: Path, project_images_dir: Path) -> dict[str, object]:
    """Extract SfM metrics from a completed pipeline run."""
    sfm_dir = run_dir / "sfm"
    sparse_txt = sfm_dir / "selected_sparse_txt"
    sparse_bin = sfm_dir / "selected_sparse"
    database = sfm_dir / "database.db"
    analyzer = _run_model_analyzer(colmap_bin=colmap_bin, sparse_model=sparse_bin)
    registered_names = _registered_image_names(sparse_txt / "images.txt")
    total_images = _count_source_images(project_images_dir)
    point_metrics = _point_metrics(sparse_txt / "points3D.txt")
    graph_metrics = _database_graph_metrics(database=database, registered_names=registered_names)
    registered_count = int(analyzer.get("registered_images") or len(registered_names))
    return {
        "registered_images": registered_count,
        "total_images": total_images,
        "registered_images_percent": _percent(registered_count, total_images),
        "sparse_model_count": _sparse_model_count(sfm_dir / "sparse"),
        "connected_components": graph_metrics["connected_components"],
        "largest_component_images": graph_metrics["largest_component_images"],
        "largest_component_percent": _percent(graph_metrics["largest_component_images"], registered_count),
        "mean_reprojection_error_px": analyzer.get("mean_reprojection_error_px"),
        "median_reprojection_error_px": point_metrics["median_reprojection_error_px"],
        "sparse_point_count": int(analyzer.get("sparse_point_count") or point_metrics["sparse_point_count"]),
        "mean_track_length": analyzer.get("mean_track_length"),
        "median_track_length": point_metrics["median_track_length"],
        "verified_image_pairs": graph_metrics["verified_image_pairs"],
        "cross_camera_verified_pairs": graph_metrics["cross_camera_verified_pairs"],
    }


def _run_model_analyzer(*, colmap_bin: str, sparse_model: Path) -> dict[str, float | int]:
    completed = subprocess.run(
        [colmap_bin, "model_analyzer", "--path", str(sparse_model)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=300,
    )
    text = completed.stdout
    patterns: dict[str, tuple[str, type]] = {
        "registered_images": (r"Registered images:\s+(\d+)", int),
        "sparse_point_count": (r"Points:\s+(\d+)", int),
        "mean_track_length": (r"Mean track length:\s+([-+0-9.eE]+)", float),
        "mean_reprojection_error_px": (r"Mean reprojection error:\s+([-+0-9.eE]+)px", float),
    }
    values: dict[str, float | int] = {}
    for key, (pattern, caster) in patterns.items():
        match = re.search(pattern, text)
        if match:
            values[key] = caster(match.group(1))
    return values


def _registered_image_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    names: set[str] = set()
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        while True:
            line = handle.readline()
            if not line:
                break
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            handle.readline()
            parts = stripped.split(maxsplit=9)
            if len(parts) == 10:
                names.add(parts[9])
    return names


def _point_metrics(path: Path) -> dict[str, float | int | None]:
    errors: list[float] = []
    track_lengths: list[int] = []
    if not path.exists():
        return {
            "sparse_point_count": 0,
            "median_reprojection_error_px": None,
            "median_track_length": None,
        }
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) < 9:
                continue
            try:
                errors.append(float(parts[7]))
                track_lengths.append(max(0, (len(parts) - 8) // 2))
            except ValueError:
                continue
    return {
        "sparse_point_count": len(track_lengths),
        "median_reprojection_error_px": statistics.median(errors) if errors else None,
        "median_track_length": statistics.median(track_lengths) if track_lengths else None,
    }


def _database_graph_metrics(*, database: Path, registered_names: set[str]) -> dict[str, int]:
    if not database.exists():
        return {"connected_components": 0, "largest_component_images": 0, "verified_image_pairs": 0, "cross_camera_verified_pairs": 0}
    with sqlite3.connect(database) as connection:
        images = {
            int(image_id): {"name": str(name), "camera_id": int(camera_id)}
            for image_id, name, camera_id in connection.execute("SELECT image_id, name, camera_id FROM images")
        }
        rows = connection.execute("SELECT pair_id FROM two_view_geometries WHERE rows > 0").fetchall()
    registered_ids = {
        image_id
        for image_id, data in images.items()
        if not registered_names or str(data["name"]) in registered_names
    }
    adjacency: dict[int, set[int]] = defaultdict(set)
    cross_camera = 0
    verified = 0
    for (pair_id,) in rows:
        image_id1, image_id2 = pair_id_to_image_ids(int(pair_id))
        if image_id1 not in registered_ids or image_id2 not in registered_ids:
            continue
        verified += 1
        adjacency[image_id1].add(image_id2)
        adjacency[image_id2].add(image_id1)
        if images[image_id1]["camera_id"] != images[image_id2]["camera_id"]:
            cross_camera += 1
    components = _component_sizes(registered_ids, adjacency)
    return {
        "connected_components": len(components),
        "largest_component_images": max(components) if components else 0,
        "verified_image_pairs": verified,
        "cross_camera_verified_pairs": cross_camera,
    }


def pair_id_to_image_ids(pair_id: int) -> tuple[int, int]:
    """Decode a COLMAP pair id."""
    image_id2 = pair_id % COLMAP_PAIR_ID_BASE
    image_id1 = (pair_id - image_id2) // COLMAP_PAIR_ID_BASE
    return image_id1, image_id2


def _component_sizes(nodes: set[int], adjacency: dict[int, set[int]]) -> list[int]:
    remaining = set(nodes)
    sizes: list[int] = []
    while remaining:
        start = remaining.pop()
        size = 1
        queue: deque[int] = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in adjacency.get(current, set()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    size += 1
                    queue.append(neighbor)
        sizes.append(size)
    return sizes


def _sparse_model_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len([child for child in path.iterdir() if child.is_dir()])


def _count_source_images(path: Path) -> int:
    suffixes = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file() and item.suffix.lower() in suffixes)


def _percent(value: int | float | None, total: int | float | None) -> float | None:
    if value is None or total in {None, 0}:
        return None
    return float(value) * 100.0 / float(total)
