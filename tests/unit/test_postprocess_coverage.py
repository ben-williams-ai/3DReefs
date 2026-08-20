"""Tests for whole-layout clipping and coverage-preserving delivery."""

from __future__ import annotations

import json
import struct
from pathlib import Path

from reefs.postprocess.coverage import apply_complete_layout, build_coverage_delivery, ply_info


def _metadata(path: Path, min_x: float, max_x: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "valid",
                "bounds": {
                    "min_x": min_x,
                    "max_x": max_x,
                    "min_y": 0,
                    "max_y": 1,
                    "min_z": -1,
                    "max_z": 1,
                    "buffer": 0.1,
                },
            }
        ),
        encoding="utf-8",
    )


def _write_ply(path: Path, points: list[tuple[float, float, float, float]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"element vertex {len(points)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property float scale_0\nend_header\n"
    ).encode("ascii")
    path.write_bytes(header + b"".join(struct.pack("<ffff", *point) for point in points))
    return path


def test_neighbour_splats_fill_scene_before_true_perimeter_is_trimmed(tmp_path: Path) -> None:
    patches = tmp_path / "patches"
    _metadata(patches / "p000" / "patch_metadata.json", 0, 1)
    _metadata(patches / "p001" / "patch_metadata.json", 0.8, 1.8)
    inputs = {
        "p000": _write_ply(tmp_path / "p000.ply", [(0.2, 0.5, 0, 1), (1.2, 0.5, 0, 2)]),
        "p001": _write_ply(tmp_path / "p001.ply", [(0.9, 0.5, 0, 3), (1.75, 0.5, 0, 4)]),
    }
    outputs = {patch_id: tmp_path / "out" / f"{patch_id}.ply" for patch_id in inputs}

    audit = apply_complete_layout(inputs, outputs, patches)

    assert ply_info(outputs["p000"]).count == 2  # p000 may fill p001's part of the scene.
    assert ply_info(outputs["p001"]).count == 1  # 1.75 is outside the complete scene.
    assert audit["lost_occupied_cells"] == 0
    assert audit["method"] == "wildflow_complete_layout_union"


def test_delivery_keeps_original_splats_and_every_occupied_cell(tmp_path: Path) -> None:
    patches = tmp_path / "patches"
    _metadata(patches / "p000" / "patch_metadata.json", 0, 1)
    _metadata(patches / "p001" / "patch_metadata.json", 0.8, 1.8)
    inputs = [
        _write_ply(tmp_path / "p000.ply", [(0.20, 0.5, 0, 1), (0.201, 0.5, 0, 2), (0.202, 0.5, 0, 3)]),
        _write_ply(tmp_path / "p001.ply", [(1.20, 0.5, 0, 4), (1.201, 0.5, 0, 5), (1.202, 0.5, 0, 6)]),
    ]
    output = tmp_path / "delivery.ply"

    audit = build_coverage_delivery(inputs, patches, 4, output)

    assert ply_info(output).count == 4
    assert audit["covered_cells_before"] == audit["covered_cells_after"] == 2
    assert audit["lost_occupied_cells"] == 0
