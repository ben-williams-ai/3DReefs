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
class CameraOrderingReport:
    """How one camera group was ordered."""

    camera: str
    method: str
    image_count: int
    first_image: str | None
    last_image: str | None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable report."""
        return {
            "camera": self.camera,
            "method": self.method,
            "image_count": self.image_count,
            "first_image": self.first_image,
            "last_image": self.last_image,
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class OrderedCameraPaths:
    """Ordered relative image paths for one camera group."""

    camera: str
    paths: list[Path]
    report: CameraOrderingReport


@dataclass(frozen=True)
class ImageSequence:
    """Ordered image sequence used by ordering-sensitive behaviours."""

    source_root: Path
    items: list[ImageItem]
    ordering_method: str
    ordering_reports: list[CameraOrderingReport] = field(default_factory=list)
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


def order_camera_paths(*, source_root: Path, camera: str, paths: list[Path]) -> OrderedCameraPaths:
    """Order one camera group's relative image paths."""
    naturally_ordered = sorted(paths, key=natural_key)
    timestamps = {relative_path: capture_timestamp(source_root / relative_path) for relative_path in naturally_ordered}
    warnings: list[str] = []
    missing = [path for path, timestamp in timestamps.items() if timestamp is None]
    if missing:
        ordered_paths = naturally_ordered
        method = "natural_path"
        warnings.append(
            "Capture metadata ordering is unavailable for "
            f"{len(missing)} image(s); used natural relative-path order."
        )
    else:
        ordered_paths = sorted(naturally_ordered, key=lambda path: (timestamps[path], natural_key(path)))
        method = "capture_metadata"
        for before, after in zip(naturally_ordered, naturally_ordered[1:]):
            before_ts = timestamps[before]
            after_ts = timestamps[after]
            if before_ts is not None and after_ts is not None and after_ts < before_ts:
                warnings.append(
                    "Natural filename order jumps backward in capture time at "
                    f"{before.as_posix()} -> {after.as_posix()}; using capture metadata order."
                )
                break

    report = CameraOrderingReport(
        camera=camera,
        method=method,
        image_count=len(ordered_paths),
        first_image=ordered_paths[0].as_posix() if ordered_paths else None,
        last_image=ordered_paths[-1].as_posix() if ordered_paths else None,
        warnings=warnings,
    )
    return OrderedCameraPaths(camera=camera, paths=ordered_paths, report=report)


def build_image_sequence(source_root: Path) -> ImageSequence:
    """Build an ordered image sequence from a single- or multi-camera root."""
    direct = image_files(source_root)
    dirs = camera_dirs(source_root)
    dirs_with_images = [camera_dir for camera_dir in dirs if image_files(camera_dir)]

    if direct and dirs:
        raise ValueError("raw_images mixes direct images and camera subfolders")
    if not direct and not dirs_with_images:
        raise ValueError(f"No supported image files found in {source_root}")

    ordered_groups: list[OrderedCameraPaths] = []
    if direct:
        ordered_groups.append(
            order_camera_paths(
                source_root=source_root,
                camera="single",
                paths=[Path(item.name) for item in direct],
            )
        )
    else:
        for camera_dir in dirs_with_images:
            ordered_groups.append(
                order_camera_paths(
                    source_root=source_root,
                    camera=camera_dir.name,
                    paths=[Path(camera_dir.name) / image.name for image in image_files(camera_dir)],
                )
            )

    items: list[ImageItem] = []
    for group in ordered_groups:
        for camera_index, relative_path in enumerate(group.paths):
            items.append(
                ImageItem(
                    relative_path=relative_path,
                    camera_group=group.camera,
                    global_index=len(items),
                    camera_index=camera_index,
                    capture_timestamp=capture_timestamp(source_root / relative_path),
                )
            )

    methods = {group.report.method for group in ordered_groups}
    ordering_method = next(iter(methods)) if len(methods) == 1 else "mixed"
    reports = [group.report for group in ordered_groups]
    warnings = [warning for report in reports for warning in report.warnings]
    return ImageSequence(
        source_root=source_root,
        items=items,
        ordering_method=ordering_method,
        ordering_reports=reports,
        ordering_warnings=warnings,
    )

