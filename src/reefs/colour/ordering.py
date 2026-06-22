"""Shared ordering helpers for image sequences."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

_NATURAL_TOKEN_RE = re.compile(r"(\d+)")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


@dataclass(frozen=True)
class ImageItem:
    """One ordered image and its output identity."""

    relative_path: Path
    camera_group: str
    global_index: int
    camera_index: int
    capture_timestamp: datetime | None = None
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class CameraGroup:
    """A top-level camera folder or the single-camera group."""

    name: str
    items: list[ImageItem]


@dataclass(frozen=True)
class ImageSequence:
    """Ordered image sequence used by ordering-sensitive behaviours."""

    source_root: Path
    items: list[ImageItem]
    ordering_method: str
    ordering_warnings: list[str] = field(default_factory=list)

    @property
    def relative_paths(self) -> list[Path]:
        """Return ordered paths relative to the source root."""
        return [item.relative_path for item in self.items]

    @property
    def camera_groups(self) -> list[CameraGroup]:
        """Return ordered camera groups."""
        grouped: dict[str, list[ImageItem]] = {}
        for item in self.items:
            grouped.setdefault(item.camera_group, []).append(item)
        return [CameraGroup(name=name, items=items) for name, items in grouped.items()]


def natural_key(path: Path | str) -> tuple[object, ...]:
    """Return a stable natural-sort key for relative image paths."""
    parts: list[object] = []
    for text in Path(path).as_posix().lower().split("/"):
        for token in _NATURAL_TOKEN_RE.split(text):
            if token.isdigit():
                parts.append(int(token))
            elif token:
                parts.append(token)
        parts.append("/")
    return tuple(parts)


def image_files(path: Path) -> list[Path]:
    """Return direct image files under `path` in natural order."""
    return sorted(
        (item for item in path.iterdir() if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES),
        key=lambda item: natural_key(item.name),
    )


def capture_timestamp(path: Path) -> datetime | None:
    """Return EXIF capture timestamp when available."""
    try:
        from PIL import ExifTags, Image

        tag_by_name = {name: tag for tag, name in ExifTags.TAGS.items()}
        with Image.open(path) as image:
            exif = image.getexif()
        raw = exif.get(tag_by_name.get("DateTimeOriginal")) or exif.get(tag_by_name.get("DateTime"))
        if not raw:
            return None
        return datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None


def camera_dirs(path: Path) -> list[Path]:
    """Return camera directories in natural order."""
    return sorted((item for item in path.iterdir() if item.is_dir()), key=lambda item: natural_key(item.name))


def build_image_sequence(source_root: Path) -> ImageSequence:
    """Build an ordered image sequence from a single- or multi-camera root."""
    direct = image_files(source_root)
    dirs = camera_dirs(source_root)
    dirs_with_images = [camera_dir for camera_dir in dirs if image_files(camera_dir)]

    if direct and dirs:
        raise ValueError("raw_images mixes direct images and camera subfolders")
    if not direct and not dirs_with_images:
        raise ValueError(f"No supported image files found in {source_root}")

    relative_paths: list[Path] = []
    if direct:
        relative_paths = [Path(item.name) for item in direct]
    else:
        for camera_dir in dirs_with_images:
            for image in image_files(camera_dir):
                relative_paths.append(Path(camera_dir.name) / image.name)

    timestamps = {
        relative_path: capture_timestamp(source_root / relative_path)
        for relative_path in relative_paths
    }
    usable_timestamps = all(value is not None for value in timestamps.values()) and len(
        set(timestamps.values())
    ) == len(timestamps)
    if usable_timestamps:
        ordered_paths = sorted(relative_paths, key=lambda item: (timestamps[item], natural_key(item)))
        ordering_method = "capture_metadata"
        warnings: list[str] = []
    else:
        ordered_paths = sorted(relative_paths, key=natural_key)
        ordering_method = "natural_path"
        warnings = ["Capture metadata ordering is unavailable or ambiguous; used natural relative-path order."]

    camera_counts: dict[str, int] = {}
    items: list[ImageItem] = []
    for index, relative_path in enumerate(ordered_paths):
        camera_group = relative_path.parts[0] if not direct else "single"
        camera_index = camera_counts.get(camera_group, 0)
        camera_counts[camera_group] = camera_index + 1
        items.append(
            ImageItem(
                relative_path=relative_path,
                camera_group=camera_group,
                global_index=index,
                camera_index=camera_index,
                capture_timestamp=timestamps[relative_path],
            )
        )

    return ImageSequence(
        source_root=source_root,
        items=items,
        ordering_method=ordering_method,
        ordering_warnings=warnings,
    )
