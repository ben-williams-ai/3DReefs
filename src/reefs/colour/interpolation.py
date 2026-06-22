"""Keyframe selection and colour parameter interpolation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from reefs.colour.filters import ColourParameterSet
from reefs.colour.ordering import ImageItem, ImageSequence


@dataclass(frozen=True)
class Keyframe:
    """A selected image and optional saved colour parameters."""

    id: str
    relative_path: Path
    camera_group: str
    global_position: int
    camera_position: int
    list_index: int
    parameters: ColourParameterSet | None = None
    edited: bool = False
    thumbnail_path: Path | None = None


def _keyframe_for_item(item: ImageItem, *, list_index: int) -> Keyframe:
    return Keyframe(
        id=f"{item.camera_group}:{item.relative_path.as_posix()}",
        relative_path=item.relative_path,
        camera_group=item.camera_group,
        global_position=item.global_index + 1,
        camera_position=item.camera_index + 1,
        list_index=list_index,
    )


def select_even_keyframes(items: list[ImageItem], count: int) -> list[Keyframe]:
    """Select keyframes centred in evenly spaced bins."""
    if count <= 0:
        raise ValueError("keyframe count must be positive")
    if not items:
        return []
    selected_count = min(count, len(items))
    selected: list[Keyframe] = []
    used: set[int] = set()
    for bucket in range(selected_count):
        centre = int((bucket + 0.5) * len(items) / selected_count - 0.5)
        index = min(len(items) - 1, max(0, centre))
        while index in used and index + 1 < len(items):
            index += 1
        while index in used and index > 0:
            index -= 1
        used.add(index)
        selected.append(_keyframe_for_item(items[index], list_index=len(selected) + 1))
    return selected


def rebuild_keyframes(
    sequence: ImageSequence,
    *,
    count: int,
    existing: list[Keyframe] | None = None,
    per_camera: bool = False,
) -> list[Keyframe]:
    """Rebuild keyframes while preserving edits for still-valid images."""
    existing_by_id = {keyframe.id: keyframe for keyframe in existing or []}
    selected: list[Keyframe] = []
    groups = sequence.camera_groups if per_camera else [type("Group", (), {"items": sequence.items})()]
    for group in groups:
        for keyframe in select_even_keyframes(group.items, count):
            previous = existing_by_id.get(keyframe.id)
            if previous and previous.edited:
                keyframe = replace(keyframe, parameters=previous.parameters, edited=True)
            selected.append(replace(keyframe, list_index=len(selected) + 1))
    return selected


def interpolate_parameters(
    sequence: ImageSequence,
    keyframes: list[Keyframe],
) -> dict[Path, ColourParameterSet]:
    """Interpolate edited keyframe parameters across the ordered sequence."""
    edited = [keyframe for keyframe in keyframes if keyframe.edited and keyframe.parameters is not None]
    if not edited:
        raise ValueError("At least one edited keyframe is required to apply colour restoration")
    item_index = {item.relative_path: item.global_index for item in sequence.items}
    edited = sorted(edited, key=lambda keyframe: item_index[keyframe.relative_path])
    if len(edited) == 1:
        return {item.relative_path: edited[0].parameters for item in sequence.items if edited[0].parameters}

    result: dict[Path, ColourParameterSet] = {}
    fields = tuple(ColourParameterSet().__dataclass_fields__)  # type: ignore[attr-defined]
    for item in sequence.items:
        position = item.global_index
        before = edited[0]
        after = edited[-1]
        for index, candidate in enumerate(edited[:-1]):
            next_candidate = edited[index + 1]
            if item_index[candidate.relative_path] <= position <= item_index[next_candidate.relative_path]:
                before = candidate
                after = next_candidate
                break
            if position < item_index[edited[0].relative_path]:
                before = after = edited[0]
                break
            if position > item_index[edited[-1].relative_path]:
                before = after = edited[-1]
                break
        start = item_index[before.relative_path]
        end = item_index[after.relative_path]
        ratio = 0.0 if start == end else (position - start) / (end - start)
        assert before.parameters is not None
        assert after.parameters is not None
        values = {
            field: getattr(before.parameters, field)
            + (getattr(after.parameters, field) - getattr(before.parameters, field)) * ratio
            for field in fields
        }
        result[item.relative_path] = ColourParameterSet(**values)
    return result
