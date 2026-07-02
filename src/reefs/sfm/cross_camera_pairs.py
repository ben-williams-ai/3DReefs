"""Cross-camera image pair generation for multi-camera SfM datasets."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from reefs.images.ordering import natural_key
from reefs.preflight.images import ImageLayout

_NUMBER_RE = re.compile(r"(\d+)")


@dataclass(frozen=True)
class CrossCameraPair:
    """One proposed pair between two camera folders."""

    left: str
    right: str
    offset: int


@dataclass(frozen=True)
class CrossCameraPairs:
    """Generated pair list and review metadata."""

    pairs: list[CrossCameraPair]
    summary: dict[str, object]


def _frame_number(path: Path) -> int | None:
    matches = _NUMBER_RE.findall(path.stem)
    return int(matches[-1]) if matches else None


def _group_images(layout: ImageLayout) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = {}
    for path in layout.relative_image_paths:
        parts = path.parts
        camera = parts[0] if len(parts) > 1 else "single"
        groups.setdefault(camera, []).append(path)
    return groups


def _index_images(paths: list[Path]) -> tuple[dict[int, Path], str, list[str]]:
    numbers = [_frame_number(path) for path in paths]
    warnings: list[str] = []
    if paths and all(number is not None for number in numbers) and len(set(numbers)) == len(numbers):
        parsed = [int(number) for number in numbers if number is not None]
        missing = max(parsed) - min(parsed) + 1 - len(parsed)
        if missing:
            warnings.append(f"missing {missing} numeric frame index(es)")
        return dict(zip(parsed, paths, strict=True)), "numeric_filename", warnings
    if any(number is None for number in numbers):
        warnings.append("non-numeric filename fallback")
    else:
        warnings.append("duplicate numeric filename index fallback")
    return dict(enumerate(paths)), "natural_order", warnings


def _ordered_groups(layout: ImageLayout, *, ordering: str) -> tuple[dict[str, list[Path]], list[str]]:
    """Return camera groups in the configured pair-generation order."""
    groups = _group_images(layout)
    if ordering == "exif_timestamp":
        warnings = []
        for camera, paths in sorted(groups.items()):
            filename_ordered = sorted(paths, key=natural_key)
            if paths != filename_ordered:
                warnings.append(f"{camera}: timestamp ordering differs from natural filename order")
        return groups, warnings
    if ordering == "filename":
        return {camera: sorted(paths, key=natural_key) for camera, paths in groups.items()}, []
    raise ValueError(f"Unsupported cross-camera pair ordering: {ordering}")


def _ordering_summary(groups: dict[str, list[Path]]) -> dict[str, dict[str, object]]:
    """Summarise the final order used for each camera."""
    return {
        camera: {
            "image_count": len(paths),
            "first_image": paths[0].as_posix() if paths else None,
            "last_image": paths[-1].as_posix() if paths else None,
        }
        for camera, paths in sorted(groups.items())
    }


def generate_cross_camera_pairs(
    layout: ImageLayout,
    *,
    index_window: int,
    ordering: str = "exif_timestamp",
) -> CrossCameraPairs:
    """Generate same-index and near-index pairs across camera folders."""
    groups, warnings = _ordered_groups(layout, ordering=ordering)
    if len(groups) < 2:
        return CrossCameraPairs(
            pairs=[],
            summary={
                "ordering": ordering,
                "camera_folders_detected": sorted(groups),
                "image_counts_per_camera": {camera: len(paths) for camera, paths in sorted(groups.items())},
                "ordered_cameras": _ordering_summary(groups),
                "filename_index_parsing_strategy": {},
                "proposed_cross_camera_pairs": 0,
                "same_index_examples": [],
                "offset_examples": [],
                "warnings": ["single-camera dataset; no cross-camera pairs generated"],
            },
        )

    indexed: dict[str, dict[int, Path]] = {}
    strategies: dict[str, str] = {}
    for camera, paths in sorted(groups.items()):
        _, strategies[camera], camera_warnings = _index_images(paths)
        indexed[camera] = dict(enumerate(paths))
        warnings.extend(f"{camera}: {warning}" for warning in camera_warnings)
    counts = {camera: len(paths) for camera, paths in sorted(groups.items())}
    if len(set(counts.values())) > 1:
        warnings.append("camera folders have unequal image counts")

    pairs_by_name: dict[tuple[str, str], CrossCameraPair] = {}
    for left_camera, right_camera in combinations(sorted(indexed), 2):
        left_by_index = indexed[left_camera]
        right_by_index = indexed[right_camera]
        for left_index, left_path in left_by_index.items():
            for offset in range(-index_window, index_window + 1):
                right_path = right_by_index.get(left_index + offset)
                if right_path is None:
                    continue
                left = left_path.as_posix()
                right = right_path.as_posix()
                pairs_by_name[(left, right)] = CrossCameraPair(left=left, right=right, offset=offset)

    pairs = list(pairs_by_name.values())
    same_examples = [pair.__dict__ for pair in pairs if pair.offset == 0][:5]
    offset_examples = [pair.__dict__ for pair in pairs if pair.offset != 0][:5]
    return CrossCameraPairs(
        pairs=pairs,
        summary={
            "ordering": ordering,
            "camera_folders_detected": sorted(groups),
            "image_counts_per_camera": counts,
            "ordered_cameras": _ordering_summary(groups),
            "filename_index_parsing_strategy": strategies,
            "source_ordering": [report.as_dict() for report in layout.ordering_reports or []],
            "proposed_cross_camera_pairs": len(pairs),
            "same_index_examples": same_examples,
            "offset_examples": offset_examples,
            "warnings": warnings,
        },
    )


def write_pairs_file(pairs: list[CrossCameraPair], path: Path) -> None:
    """Write COLMAP matches_importer pair-list format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{pair.left} {pair.right}" for pair in pairs) + "\n", encoding="utf-8")


def _sample_evenly(items: list[CrossCameraPair], count: int) -> list[CrossCameraPair]:
    """Return up to count items spread across the full sequence."""
    if count <= 0 or len(items) <= count:
        return items
    if count == 1:
        return [items[len(items) // 2]]
    indexes = [round(index * (len(items) - 1) / (count - 1)) for index in range(count)]
    sampled: list[CrossCameraPair] = []
    seen: set[int] = set()
    for index in indexes:
        if index not in seen:
            sampled.append(items[index])
            seen.add(index)
    return sampled


def write_pair_preview(result: CrossCameraPairs, *, preview_path: Path, summary_path: Path, preview_count: int) -> None:
    """Write a short pair preview and JSON summary."""
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_lines = [f"{pair.left} {pair.right}" for pair in _sample_evenly(result.pairs, preview_count)]
    preview_path.write_text("\n".join(preview_lines) + ("\n" if preview_lines else ""), encoding="utf-8")
    summary_path.write_text(json.dumps(result.summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
