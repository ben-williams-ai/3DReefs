"""Image collection diagnostics used before expensive SfM stages."""

from __future__ import annotations

import struct
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from reefs.colour.ordering import natural_key
from reefs.preflight.images import IMAGE_SUFFIXES, ImageLayout


@dataclass(frozen=True)
class CameraDimensionReport:
    """Image dimensions detected for one camera group."""

    camera: str
    dimensions: dict[tuple[int, int], list[Path]]

    @property
    def is_consistent(self) -> bool:
        """Return whether all images have one dimension."""
        return len(self.dimensions) == 1

    @property
    def image_count(self) -> int:
        """Return total image count for the camera group."""
        return sum(len(paths) for paths in self.dimensions.values())

    @property
    def primary_dimension(self) -> tuple[int, int] | None:
        """Return the only dimension when consistent."""
        if not self.is_consistent:
            return None
        return next(iter(self.dimensions))

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable report."""
        return {
            "camera": self.camera,
            "image_count": self.image_count,
            "dimensions": {
                f"{width}x{height}": {
                    "count": len(paths),
                    "examples": [str(path) for path in paths[:10]],
                }
                for (width, height), paths in self.dimensions.items()
            },
            "consistent": self.is_consistent,
        }


def image_dimensions(path: Path) -> tuple[int, int]:
    """Read image dimensions from JPEG or PNG headers."""
    suffix = path.suffix.lower()
    with path.open("rb") as handle:
        header = handle.read(32)
        if suffix == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"):
            width, height = struct.unpack(">II", header[16:24])
            return int(width), int(height)
        if suffix in {".jpg", ".jpeg"}:
            handle.seek(0)
            if handle.read(2) != b"\xff\xd8":
                raise ValueError(f"JPEG image has invalid SOI marker: {path}")
            while True:
                marker_start = handle.read(1)
                if not marker_start:
                    break
                if marker_start != b"\xff":
                    continue
                marker = handle.read(1)
                while marker == b"\xff":
                    marker = handle.read(1)
                if marker in {b"\xd8", b"\xd9"}:
                    continue
                length_bytes = handle.read(2)
                if len(length_bytes) != 2:
                    break
                segment_length = struct.unpack(">H", length_bytes)[0]
                if marker in {
                    b"\xc0",
                    b"\xc1",
                    b"\xc2",
                    b"\xc3",
                    b"\xc5",
                    b"\xc6",
                    b"\xc7",
                    b"\xc9",
                    b"\xca",
                    b"\xcb",
                    b"\xcd",
                    b"\xce",
                    b"\xcf",
                }:
                    segment = handle.read(segment_length - 2)
                    if len(segment) < 5:
                        break
                    height, width = struct.unpack(">HH", segment[1:5])
                    return int(width), int(height)
                handle.seek(segment_length - 2, 1)
    raise ValueError(f"Unsupported or unreadable image dimensions: {path}")


def camera_name_for_relative_path(layout: ImageLayout, relative_path: Path) -> str:
    """Return the camera group name for a relative image path."""
    if layout.kind == "single":
        return "single"
    return relative_path.parts[0]


def group_images_by_camera(layout: ImageLayout) -> dict[str, list[Path]]:
    """Group relative image paths by camera."""
    grouped: dict[str, list[Path]] = defaultdict(list)
    for relative_path in layout.relative_image_paths:
        grouped[camera_name_for_relative_path(layout, relative_path)].append(relative_path)
    return {camera: sorted(paths, key=natural_key) for camera, paths in grouped.items()}


def dimension_reports(*, raw_images: Path, layout: ImageLayout) -> list[CameraDimensionReport]:
    """Build per-camera image dimension reports."""
    reports: list[CameraDimensionReport] = []
    for camera, relative_paths in group_images_by_camera(layout).items():
        dimensions: dict[tuple[int, int], list[Path]] = defaultdict(list)
        for relative_path in relative_paths:
            full_path = raw_images / relative_path
            if full_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            dimensions[image_dimensions(full_path)].append(relative_path)
        reports.append(CameraDimensionReport(camera=camera, dimensions=dict(dimensions)))
    return reports


def write_dimension_report(reports: list[CameraDimensionReport], report_path: Path) -> None:
    """Write a concise dimension diagnostic report."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Image Dimension Diagnostics", ""]
    for report in reports:
        lines.append(f"## Camera `{report.camera}`")
        lines.append(f"- Images: {report.image_count}")
        lines.append(f"- Consistent: {report.is_consistent}")
        for (width, height), paths in report.dimensions.items():
            lines.append(f"- {width}x{height}: {len(paths)} images")
            for path in paths[:10]:
                lines.append(f"  - {path}")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
