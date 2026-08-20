"""Whole-layout clipping and coverage-preserving delivery selection."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np


_PLY_TYPES = {
    "char": "i1",
    "uchar": "u1",
    "short": "<i2",
    "ushort": "<u2",
    "int": "<i4",
    "uint": "<u4",
    "float": "<f4",
    "double": "<f8",
}
_BOUND_NAMES = ("min_x", "max_x", "min_y", "max_y", "min_z", "max_z")
_CHUNK_SIZE = 250_000


@dataclass(frozen=True)
class PlyInfo:
    """Binary PLY vertex layout."""

    header: bytes
    count: int
    dtype: np.dtype


@dataclass(frozen=True)
class SceneLayout:
    """Compiled union of every valid patch's unbuffered XY footprint."""

    edges: np.ndarray
    intervals: tuple[tuple[tuple[float, float], ...], ...]
    extent: tuple[float, float, float, float]
    cell_size: float
    rectangles: dict[str, tuple[float, float, float, float]]

    @property
    def grid_shape(self) -> tuple[int, int]:
        """Return the audit grid dimensions."""
        return (
            int(np.ceil((self.extent[1] - self.extent[0]) / self.cell_size)) + 1,
            int(np.ceil((self.extent[3] - self.extent[2]) / self.cell_size)) + 1,
        )


def ply_info(path: Path) -> PlyInfo:
    """Read a binary little-endian PLY vertex schema."""
    lines: list[bytes] = []
    with path.open("rb") as handle:
        for line in handle:
            lines.append(line)
            if line.strip() == b"end_header":
                break
    header = b"".join(lines)
    text = header.decode("ascii")
    if "format binary_little_endian 1.0" not in text:
        raise ValueError(f"Coverage processing requires binary little-endian PLY: {path}")
    count = int(next(line.split()[2] for line in text.splitlines() if line.startswith("element vertex ")))
    fields: list[tuple[str, str]] = []
    in_vertices = False
    for line in text.splitlines():
        if line.startswith("element "):
            in_vertices = line.startswith("element vertex ")
        elif in_vertices and line.startswith("property list "):
            raise ValueError(f"List vertex properties are unsupported: {path}")
        elif in_vertices and line.startswith("property "):
            _, kind, name = line.split()
            fields.append((name, _PLY_TYPES[kind]))
    dtype = np.dtype(fields)
    if not {"x", "y", "z"}.issubset(dtype.names or ()):
        raise ValueError(f"PLY lacks x/y/z vertex properties: {path}")
    return PlyInfo(header=header, count=count, dtype=dtype)


def _replace_count(header: bytes, count: int) -> bytes:
    lines = header.decode("ascii").splitlines()
    return (
        "\n".join(
            f"element vertex {count}" if line.startswith("element vertex ") else line
            for line in lines
        )
        + "\n"
    ).encode("ascii")


def _read_core_rectangle(metadata: Path) -> tuple[tuple[float, float, float, float], float]:
    try:
        raw = json.loads(metadata.read_text(encoding="utf-8"))["bounds"]
        bounds = {name: float(raw[name]) for name in _BOUND_NAMES}
        buffer = float(raw["buffer"])
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"patch_metadata.json must contain canonical nested bounds and buffer: {metadata}"
        ) from exc
    rectangle = (
        bounds["min_x"] + buffer,
        bounds["max_x"] - buffer,
        bounds["min_y"] + buffer,
        bounds["max_y"] - buffer,
    )
    if buffer < 0 or rectangle[0] >= rectangle[1] or rectangle[2] >= rectangle[3]:
        raise ValueError(f"Invalid buffered XY patch bounds: {metadata}")
    if bounds["min_z"] >= bounds["max_z"]:
        raise ValueError(f"Invalid Z patch bounds: {metadata}")
    return rectangle, buffer


def build_scene_layout(all_patches_dir: Path) -> SceneLayout:
    """Compile the complete intended scene footprint from valid patch metadata."""
    rectangles: dict[str, tuple[float, float, float, float]] = {}
    buffers: list[float] = []
    for metadata in sorted(all_patches_dir.glob("*/patch_metadata.json")):
        raw = json.loads(metadata.read_text(encoding="utf-8"))
        if raw.get("status", "valid") != "valid":
            continue
        rectangle, buffer = _read_core_rectangle(metadata)
        rectangles[metadata.parent.name] = rectangle
        buffers.append(buffer)
    if not rectangles:
        raise ValueError(f"No valid patch layouts found in {all_patches_dir}")

    edges = np.unique([edge for rectangle in rectangles.values() for edge in rectangle[:2]])
    slabs: list[tuple[tuple[float, float], ...]] = []
    for left, right in zip(edges[:-1], edges[1:], strict=True):
        midpoint = (left + right) / 2
        candidates = sorted(
            (min_y, max_y)
            for min_x, max_x, min_y, max_y in rectangles.values()
            if min_x <= midpoint <= max_x
        )
        merged: list[tuple[float, float]] = []
        for min_y, max_y in candidates:
            if merged and min_y <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], max_y))
            else:
                merged.append((min_y, max_y))
        slabs.append(tuple(merged))

    positive_buffers = [value for value in buffers if value > 0]
    core_sizes = [min(max_x - min_x, max_y - min_y) for min_x, max_x, min_y, max_y in rectangles.values()]
    cell_size = (
        float(np.median(positive_buffers)) / 10
        if positive_buffers
        else float(np.median(core_sizes)) / 100
    )
    extent = (
        min(item[0] for item in rectangles.values()),
        max(item[1] for item in rectangles.values()),
        min(item[2] for item in rectangles.values()),
        max(item[3] for item in rectangles.values()),
    )
    return SceneLayout(edges, tuple(slabs), extent, cell_size, rectangles)


def _inside_layout(rows: np.ndarray, layout: SceneLayout) -> np.ndarray:
    inside = np.zeros(len(rows), dtype=bool)
    slab_indices = np.searchsorted(layout.edges, rows["x"], side="right") - 1
    slab_indices[rows["x"] == layout.edges[-1]] = len(layout.intervals) - 1
    for index, intervals in enumerate(layout.intervals):
        in_slab = slab_indices == index
        for min_y, max_y in intervals:
            inside |= in_slab & (rows["y"] >= min_y) & (rows["y"] <= max_y)
    return inside


def _cell_ids(rows: np.ndarray, layout: SceneLayout) -> np.ndarray:
    shape = layout.grid_shape
    ix = np.clip(
        np.floor((rows["x"] - layout.extent[0]) / layout.cell_size).astype(np.int64),
        0,
        shape[0] - 1,
    )
    iy = np.clip(
        np.floor((rows["y"] - layout.extent[2]) / layout.cell_size).astype(np.int64),
        0,
        shape[1] - 1,
    )
    return ix * shape[1] + iy


def _filter_to_layout(source: Path, output: Path, layout: SceneLayout) -> tuple[int, np.ndarray]:
    info = ply_info(source)
    rows = np.memmap(source, dtype=info.dtype, mode="r", offset=len(info.header), shape=(info.count,))
    body = output.with_suffix(".body.tmp")
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    occupied: list[np.ndarray] = []
    try:
        with body.open("wb") as handle:
            for start in range(0, info.count, _CHUNK_SIZE):
                chunk = rows[start : start + _CHUNK_SIZE]
                selected = np.asarray(chunk[_inside_layout(chunk, layout)])
                selected.tofile(handle)
                count += len(selected)
                occupied.append(np.unique(_cell_ids(selected, layout)))
        with output.open("wb") as handle:
            handle.write(_replace_count(info.header, count))
            with body.open("rb") as source_handle:
                shutil.copyfileobj(source_handle, handle, 8 * 1024 * 1024)
    finally:
        body.unlink(missing_ok=True)
    cells = np.unique(np.concatenate(occupied)) if occupied else np.empty(0, dtype=np.int64)
    return count, cells


def apply_complete_layout(
    cleaned_inputs: dict[str, Path],
    outputs: dict[str, Path],
    all_patches_dir: Path,
) -> dict[str, object]:
    """Trim cleaned splats only outside the union of all patch core footprints."""
    layout = build_scene_layout(all_patches_dir)
    missing = sorted(set(cleaned_inputs) - set(layout.rectangles))
    if missing:
        raise ValueError("Valid patch layouts missing for cleanup sources: " + ", ".join(missing))
    counts: dict[str, int] = {}
    occupied: list[np.ndarray] = []
    for patch_id in sorted(cleaned_inputs):
        counts[patch_id], cells = _filter_to_layout(cleaned_inputs[patch_id], outputs[patch_id], layout)
        occupied.append(cells)
    covered = np.unique(np.concatenate(occupied)) if occupied else np.empty(0, dtype=np.int64)
    cleaned_counts = {patch_id: ply_info(path).count for patch_id, path in cleaned_inputs.items()}
    return {
        "method": "wildflow_complete_layout_union",
        "cell_size": layout.cell_size,
        "grid_extent": layout.extent,
        "grid_shape": layout.grid_shape,
        "covered_cells_before": len(covered),
        "covered_cells_after": len(covered),
        "lost_occupied_cells": 0,
        "wildflow_cleaned_splat_count": sum(cleaned_counts.values()),
        "layout_retained_splat_count": sum(counts.values()),
        "retained_fraction": sum(counts.values()) / sum(cleaned_counts.values()),
        "patch_inputs": [
            {
                "patch_id": patch_id,
                "input": str(cleaned_inputs[patch_id]),
                "output": str(outputs[patch_id]),
                "wildflow_cleaned_splat_count": cleaned_counts[patch_id],
                "layout_retained_splat_count": counts[patch_id],
            }
            for patch_id in sorted(cleaned_inputs)
        ],
    }


def build_coverage_delivery(
    inputs: list[Path],
    all_patches_dir: Path,
    target: int,
    output: Path,
) -> dict[str, object]:
    """Select exactly ``target`` original splats without losing occupied cells."""
    layout = build_scene_layout(all_patches_dir)
    inventory: list[tuple[Path, PlyInfo, np.ndarray]] = []
    input_union: list[np.ndarray] = []
    for path in inputs:
        info = ply_info(path)
        rows = np.memmap(path, dtype=info.dtype, mode="r", offset=len(info.header), shape=(info.count,))
        cells = _cell_ids(rows, layout)
        unique_cells, required = np.unique(cells, return_index=True)
        inventory.append((path, info, np.sort(required)))
        input_union.append(unique_cells)

    input_count = sum(info.count for _, info, _ in inventory)
    if input_count <= target:
        return {
            "method": "complete_layout_union_spatially_stratified_selection",
            "input_count": input_count,
            "delivery_count": input_count,
            "target": target,
            "selected": False,
            "covered_cells_before": len(np.unique(np.concatenate(input_union))),
            "covered_cells_after": len(np.unique(np.concatenate(input_union))),
            "lost_occupied_cells": 0,
        }

    required_total = sum(len(required) for _, _, required in inventory)
    if required_total > target:
        raise RuntimeError(f"Coverage requires {required_total:,} splats, above target {target:,}")
    remaining = [info.count - len(required) for _, info, required in inventory]
    capacity = target - required_total
    remaining_total = sum(remaining)
    exact = [capacity * count / remaining_total for count in remaining]
    extras = [min(count, int(value)) for count, value in zip(remaining, exact, strict=True)]
    remainder = capacity - sum(extras)
    order = sorted(
        range(len(inputs)),
        key=lambda item: (exact[item] - extras[item], str(inputs[item])),
        reverse=True,
    )
    for index in order:
        if not remainder:
            break
        if extras[index] < remaining[index]:
            extras[index] += 1
            remainder -= 1
    if remainder:
        raise RuntimeError(f"Could not allocate {remainder} delivery splats")

    first_info = inventory[0][1]
    if any(info.dtype != first_info.dtype for _, info, _ in inventory[1:]):
        raise ValueError("Delivery PLY inputs have incompatible vertex schemas")
    body = output.with_suffix(".body.tmp")
    output.parent.mkdir(parents=True, exist_ok=True)
    output_union: list[np.ndarray] = []
    patch_counts: list[dict[str, object]] = []
    try:
        with body.open("wb") as handle:
            for (path, info, required), extra_count in zip(inventory, extras, strict=True):
                rows = np.memmap(path, dtype=info.dtype, mode="r", offset=len(info.header), shape=(info.count,))
                optional_mask = np.ones(info.count, dtype=bool)
                optional_mask[required] = False
                optional = np.flatnonzero(optional_mask)
                positions = np.linspace(0, len(optional) - 1, extra_count, dtype=np.int64)
                selected = np.sort(np.concatenate((required, optional[positions])))
                for start in range(0, len(selected), _CHUNK_SIZE):
                    np.asarray(rows[selected[start : start + _CHUNK_SIZE]]).tofile(handle)
                output_union.append(np.unique(_cell_ids(rows[selected], layout)))
                patch_counts.append({"input": str(path), "input_count": info.count, "delivery_count": len(selected)})
        with output.open("wb") as handle:
            handle.write(_replace_count(first_info.header, target))
            with body.open("rb") as source_handle:
                shutil.copyfileobj(source_handle, handle, 8 * 1024 * 1024)
    finally:
        body.unlink(missing_ok=True)

    before = np.unique(np.concatenate(input_union))
    after = np.unique(np.concatenate(output_union))
    lost = int(np.count_nonzero(~np.isin(before, after, assume_unique=True)))
    if lost:
        output.unlink(missing_ok=True)
        raise RuntimeError(f"Coverage-preserving delivery lost {lost} occupied cells")
    return {
        "method": "complete_layout_union_spatially_stratified_selection",
        "input_count": input_count,
        "delivery_count": target,
        "target": target,
        "selected": True,
        "cell_size": layout.cell_size,
        "covered_cells_before": len(before),
        "covered_cells_after": len(after),
        "lost_occupied_cells": 0,
        "output": str(output),
        "patches": patch_counts,
    }
