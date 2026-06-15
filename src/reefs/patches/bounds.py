"""Scene-relative patch extent helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass

from reefs.patches.artefacts import SparseImage


@dataclass(frozen=True)
class PatchBounds:
    """Relative scene-coordinate patch bounds."""

    patch_id: str
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_z: float
    max_z: float
    buffer: float

    def contains_point(self, xyz: tuple[float, float, float]) -> bool:
        """Return whether a point lies inside the buffered patch bounds."""
        x, y, z = xyz
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y and self.min_z <= z <= self.max_z

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable bounds record."""
        return {
            "min_x": self.min_x,
            "max_x": self.max_x,
            "min_y": self.min_y,
            "max_y": self.max_y,
            "min_z": self.min_z,
            "max_z": self.max_z,
            "buffer": self.buffer,
        }


def _axis_extent(values: list[float], buffer: float) -> tuple[float, float]:
    minimum = min(values)
    maximum = max(values)
    span = maximum - minimum
    pad = max(span * buffer, buffer if span == 0 else 0.0)
    return minimum - pad, maximum + pad


def generate_patch_bounds(
    images: list[SparseImage],
    *,
    max_cameras: int,
    buffer: float,
    points_xyz: list[tuple[float, float, float]] | None = None,
) -> list[PatchBounds]:
    """Generate deterministic scene-relative patch bounds from camera centres."""
    if max_cameras <= 0:
        raise ValueError("max_cameras must be positive")
    if not images:
        raise ValueError("Cannot generate patch bounds without registered images")

    sorted_images = sorted(images, key=lambda image: (image.center[0], image.name))
    patch_count = max(1, math.ceil(len(sorted_images) / max_cameras))
    support_points = points_xyz or []
    global_y_values = [image.center[1] for image in sorted_images] + [point[1] for point in support_points]
    global_z_values = [image.center[2] for image in sorted_images] + [point[2] for point in support_points]
    global_y = _axis_extent(global_y_values, buffer)
    global_z = _axis_extent(global_z_values, buffer)
    bounds: list[PatchBounds] = []
    for index in range(patch_count):
        start = index * max_cameras
        stop = min(len(sorted_images), (index + 1) * max_cameras)
        chunk = sorted_images[start:stop]
        chunk_x_values = [image.center[0] for image in chunk]
        if support_points and patch_count == 1:
            chunk_x_values.extend(point[0] for point in support_points)
        min_x, max_x = _axis_extent(chunk_x_values, buffer)
        bounds.append(
            PatchBounds(
                patch_id=f"p{index:03d}",
                min_x=min_x,
                max_x=max_x,
                min_y=global_y[0],
                max_y=global_y[1],
                min_z=global_z[0],
                max_z=global_z[1],
                buffer=buffer,
            )
        )
    return bounds
