"""Intrinsics selection and COLMAP cameras.txt validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reefs.diagnostics.images import CameraDimensionReport, group_images_by_camera
from reefs.preflight.images import ImageLayout


@dataclass(frozen=True)
class IntrinsicsSelection:
    """Chosen intrinsics handling for one SfM run."""

    source: str
    camera_model: str | None
    selected_images: dict[str, list[str]]
    warnings: list[str]
    user_cameras_file: Path | None = None
    camera_params: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable intrinsics selection."""
        return {
            "source": self.source,
            "camera_model": self.camera_model,
            "selected_images": self.selected_images,
            "warnings": self.warnings,
            "user_cameras_file": str(self.user_cameras_file) if self.user_cameras_file else None,
            "camera_params": self.camera_params,
        }


def select_calibration_images(
    *,
    layout: ImageLayout,
    selection_start_index: int,
    selection_end_index: int,
) -> tuple[dict[str, list[str]], list[str]]:
    """Select per-camera images for intrinsics pre-calculation."""
    selected: dict[str, list[str]] = {}
    warnings: list[str] = []
    for camera, images in group_images_by_camera(layout).items():
        window = images[selection_start_index:selection_end_index]
        if not window:
            window = images
            warnings.append(
                f"Camera {camera} has too few images for the default intrinsics window; "
                f"using all {len(window)} available images."
            )
        if not window:
            raise ValueError(f"Camera {camera} has no valid images for intrinsics selection")
        selected[camera] = [str(path) for path in window]
    return selected, warnings


def parse_cameras_txt(path: Path) -> list[dict[str, object]]:
    """Parse non-comment COLMAP cameras.txt lines."""
    if not path.exists() or not path.is_file():
        raise ValueError(f"User cameras.txt does not exist: {path}")
    cameras: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) < 5:
                raise ValueError(f"Malformed cameras.txt line: {stripped}")
            try:
                cameras.append(
                    {
                        "camera_id": int(parts[0]),
                        "model": parts[1],
                        "width": int(parts[2]),
                        "height": int(parts[3]),
                        "params": [float(value) for value in parts[4:]],
                    }
                )
            except ValueError as exc:
                raise ValueError(f"Malformed cameras.txt numeric value: {stripped}") from exc
    if not cameras:
        raise ValueError(f"User cameras.txt contains no cameras: {path}")
    return cameras


def validate_cameras_txt(
    *,
    cameras_txt: Path,
    dimension_reports: list[CameraDimensionReport],
) -> None:
    """Validate a user-supplied COLMAP cameras.txt against camera groups."""
    cameras = parse_cameras_txt(cameras_txt)
    if len(cameras) != len(dimension_reports):
        raise ValueError(
            f"User cameras.txt has {len(cameras)} cameras but image layout has "
            f"{len(dimension_reports)} camera groups"
        )
    expected_dimensions = sorted(report.primary_dimension for report in dimension_reports)
    actual_dimensions = sorted((camera["width"], camera["height"]) for camera in cameras)
    if expected_dimensions != actual_dimensions:
        raise ValueError(
            "User cameras.txt dimensions do not match detected image dimensions: "
            f"expected {expected_dimensions}, got {actual_dimensions}"
        )


def camera_params_from_cameras_txt(path: Path) -> str:
    """Return COLMAP camera params from the first camera in cameras.txt."""
    cameras = parse_cameras_txt(path)
    return ",".join(str(value) for value in cameras[0]["params"])


def choose_intrinsics(
    *,
    layout: ImageLayout,
    dimension_reports: list[CameraDimensionReport],
    camera_model: str,
    precalculate: bool,
    cameras_txt: Path | None,
    selection_start_index: int,
    selection_end_index: int,
) -> IntrinsicsSelection:
    """Choose and validate intrinsics source."""
    if cameras_txt is not None:
        validate_cameras_txt(cameras_txt=cameras_txt, dimension_reports=dimension_reports)
        return IntrinsicsSelection(
            source="user_cameras_file",
            camera_model=None,
            selected_images={},
            warnings=[],
            user_cameras_file=cameras_txt,
            camera_params=camera_params_from_cameras_txt(cameras_txt),
        )
    selected_images: dict[str, list[str]] = {}
    warnings: list[str] = []
    if precalculate:
        selected_images, warnings = select_calibration_images(
            layout=layout,
            selection_start_index=selection_start_index,
            selection_end_index=selection_end_index,
        )
    return IntrinsicsSelection(
        source="precalculated" if precalculate else "colmap_default_initialisation",
        camera_model=camera_model,
        selected_images=selected_images,
        warnings=warnings,
        user_cameras_file=None,
        camera_params=None,
    )
