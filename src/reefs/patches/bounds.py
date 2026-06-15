"""Scene-relative patch extent helpers."""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from reefs.patches.artefacts import SparseImage


@dataclass(frozen=True)
class PatchBoundsToolValidation:
    """Wildflow patch extent validation result."""

    status: str
    backend: str
    message: str

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable validation result."""
        return {"status": self.status, "backend": self.backend, "message": self.message}


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

    @property
    def centre(self) -> tuple[float, float]:
        """Return patch centre in scene XY coordinates."""
        return ((self.min_x + self.max_x) / 2.0, (self.min_y + self.max_y) / 2.0)

    @property
    def width(self) -> float:
        """Return patch width in scene-relative units."""
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        """Return patch height in scene-relative units."""
        return self.max_y - self.min_y

    def contains_xy(self, x: float, y: float) -> bool:
        """Return whether an XY location lies inside the patch bounds."""
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y

    def is_boundary_xy(self, x: float, y: float) -> bool:
        """Return whether an XY location lies inside the buffered boundary band."""
        if not self.contains_xy(x, y):
            return False
        inner_min_x = self.min_x + self.buffer
        inner_max_x = self.max_x - self.buffer
        inner_min_y = self.min_y + self.buffer
        inner_max_y = self.max_y - self.buffer
        if inner_min_x >= inner_max_x or inner_min_y >= inner_max_y:
            return True
        return not (inner_min_x <= x <= inner_max_x and inner_min_y <= y <= inner_max_y)

    def contains_point(self, xyz: tuple[float, float, float]) -> bool:
        """Return whether a point lies inside the buffered patch bounds."""
        x, y, z = xyz
        return self.contains_xy(x, y) and self.min_z <= z <= self.max_z

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


def validate_patch_bounds_backend() -> PatchBoundsToolValidation:
    """Validate wildflow patch extent generation without running patching."""
    try:
        module = importlib.import_module("wildflow.splat")
    except ImportError:
        return PatchBoundsToolValidation("failed", "wildflow", "wildflow is not installed")
    if not callable(getattr(module, "patches", None)):
        return PatchBoundsToolValidation("failed", "wildflow", "wildflow.splat.patches is required")
    return PatchBoundsToolValidation("passed", "wildflow", "wildflow patch generation is available")


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
    """Generate wildflow scene-relative patch bounds from camera centres."""
    if max_cameras <= 0:
        raise ValueError("max_cameras must be positive")
    if not images:
        raise ValueError("Cannot generate patch bounds without registered images")

    module = importlib.import_module("wildflow.splat")
    if not callable(getattr(module, "patches", None)):
        raise ValueError("wildflow.splat.patches is required for splat patch generation")

    sorted_images = sorted(images, key=lambda image: image.image_id)
    support_points = points_xyz or []
    global_z_values = [image.center[2] for image in sorted_images] + [point[2] for point in support_points]
    global_z = _axis_extent(global_z_values, buffer)
    patches = module.patches(
        [(float(image.center[0]), float(image.center[1])) for image in sorted_images],
        max_cameras=max_cameras,
        buffer_meters=buffer,
    )
    if not patches:
        raise ValueError("wildflow.splat.patches did not return any patch bounds")

    bounds: list[PatchBounds] = []
    for index, patch in enumerate(patches):
        try:
            bounds.append(
                PatchBounds(
                    patch_id=f"p{index:03d}",
                    min_x=float(patch["min_x"]),
                    max_x=float(patch["max_x"]),
                    min_y=float(patch["min_y"]),
                    max_y=float(patch["max_y"]),
                    min_z=global_z[0],
                    max_z=global_z[1],
                    buffer=buffer,
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid wildflow patch bounds at index {index}: {patch}") from exc
    return bounds
