"""Camera-source metadata diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reefs.diagnostics.images import group_images_by_camera
from reefs.preflight.images import ImageLayout


@dataclass(frozen=True)
class CameraSourceReport:
    """Camera-source consistency result for one camera group."""

    camera: str
    status: str
    sources: dict[str, list[Path]]

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable report."""
        return {
            "camera": self.camera,
            "status": self.status,
            "sources": {
                source: [str(path) for path in paths[:10]] for source, paths in self.sources.items()
            },
        }


def camera_source_reports(*, layout: ImageLayout) -> list[CameraSourceReport]:
    """Report camera-source consistency from layout-level evidence.

    Feature 2 avoids EXIF dependency by default. When no richer metadata reader is
    available, source consistency is reported as unknown rather than failing.
    """
    return [
        CameraSourceReport(camera=camera, status="unknown", sources={})
        for camera in group_images_by_camera(layout)
    ]
