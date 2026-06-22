"""Intrinsics selection and COLMAP cameras.txt validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reefs.diagnostics.images import CameraDimensionReport, group_images_by_camera
from reefs.preflight.images import ImageLayout


@dataclass(frozen=True)
class CameraIntrinsics:
    """COLMAP intrinsics for one shared camera model."""

    camera_id: int
    model: str
    width: int
    height: int
    params: tuple[float, ...]

    def camera_params_string(self) -> str:
        """Return params in COLMAP ImageReader.camera_params format."""
        return ",".join(str(value) for value in self.params)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable camera-intrinsics record."""
        return {
            "camera_id": self.camera_id,
            "model": self.model,
            "width": self.width,
            "height": self.height,
            "params": list(self.params),
        }


@dataclass(frozen=True)
class IntrinsicsSelection:
    """Chosen intrinsics handling for one SfM run."""

    source: str
    camera_model: str | None
    selected_images: dict[str, list[str]]
    warnings: list[str]
    user_cameras_file: Path | None = None
    camera_params: str | None = None
    camera_intrinsics_by_group: dict[str, CameraIntrinsics] | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable intrinsics selection."""
        return {
            "source": self.source,
            "camera_model": self.camera_model,
            "selected_images": self.selected_images,
            "warnings": self.warnings,
            "user_cameras_file": str(self.user_cameras_file) if self.user_cameras_file else None,
            "camera_params": self.camera_params,
            "camera_intrinsics_by_group": {
                group: intrinsics.as_dict()
                for group, intrinsics in (self.camera_intrinsics_by_group or {}).items()
            }
            or None,
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


def parse_cameras_txt(path: Path) -> list[CameraIntrinsics]:
    """Parse non-comment COLMAP cameras.txt lines."""
    if not path.exists() or not path.is_file():
        raise ValueError(f"User cameras.txt does not exist: {path}")
    cameras: list[CameraIntrinsics] = []
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
                    CameraIntrinsics(
                        camera_id=int(parts[0]),
                        model=parts[1],
                        width=int(parts[2]),
                        height=int(parts[3]),
                        params=tuple(float(value) for value in parts[4:]),
                    )
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
    actual_dimensions = sorted((camera.width, camera.height) for camera in cameras)
    if expected_dimensions != actual_dimensions:
        raise ValueError(
            "User cameras.txt dimensions do not match detected image dimensions: "
            f"expected {expected_dimensions}, got {actual_dimensions}"
        )


def _camera_intrinsics_by_dimension_report_order(
    *,
    cameras_txt: Path,
    dimension_reports: list[CameraDimensionReport],
) -> dict[str, CameraIntrinsics]:
    """Map user cameras.txt rows to camera groups by sorted camera ID and name."""
    cameras = sorted(parse_cameras_txt(cameras_txt), key=lambda camera: camera.camera_id)
    reports = sorted(dimension_reports, key=lambda report: report.camera)
    return {report.camera: camera for report, camera in zip(reports, cameras, strict=True)}


def camera_params_from_cameras_txt(path: Path) -> str:
    """Return COLMAP camera params from a single-camera cameras.txt."""
    cameras = parse_cameras_txt(path)
    if len(cameras) != 1:
        raise ValueError(
            "ImageReader.camera_params is only safe for one camera; "
            f"{path} contains {len(cameras)} cameras"
        )
    return cameras[0].camera_params_string()


def _camera_group_from_image_name(name: str) -> str:
    """Return the pipeline camera group for a COLMAP image name."""
    parts = Path(name).parts
    return parts[0] if len(parts) > 1 else "single"


def parse_images_camera_groups_txt(path: Path) -> dict[str, set[int]]:
    """Parse COLMAP images.txt into camera group -> camera IDs."""
    if not path.exists() or not path.is_file():
        raise ValueError(f"COLMAP images.txt does not exist: {path}")
    groups: dict[str, set[int]] = {}
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        while True:
            line = handle.readline()
            if not line:
                break
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) < 10:
                raise ValueError(f"Malformed COLMAP images.txt image line: {stripped}")
            try:
                camera_id = int(parts[8])
            except ValueError:
                raise ValueError(f"Malformed COLMAP images.txt camera ID: {stripped}") from None
            group = _camera_group_from_image_name(parts[9])
            groups.setdefault(group, set()).add(camera_id)
            # COLMAP text models store one points2D line after each image line.
            # Consume it explicitly so feature coordinate rows are never parsed as
            # image headers when they happen to contain many numeric fields.
            handle.readline()
    if not groups:
        raise ValueError(f"COLMAP images.txt contains no image camera assignments: {path}")
    return groups


def camera_intrinsics_by_group_from_sparse_text(
    *,
    cameras_txt: Path,
    images_txt: Path,
) -> dict[str, CameraIntrinsics]:
    """Map each pipeline camera group to its reconstructed COLMAP intrinsics."""
    cameras_by_id = {camera.camera_id: camera for camera in parse_cameras_txt(cameras_txt)}
    group_camera_ids = parse_images_camera_groups_txt(images_txt)
    intrinsics_by_group: dict[str, CameraIntrinsics] = {}
    for group, camera_ids in sorted(group_camera_ids.items()):
        if len(camera_ids) != 1:
            raise ValueError(
                f"Camera group {group!r} maps to multiple COLMAP camera IDs: "
                f"{sorted(camera_ids)}"
            )
        camera_id = next(iter(camera_ids))
        if camera_id not in cameras_by_id:
            raise ValueError(
                f"Camera group {group!r} references missing COLMAP camera ID {camera_id}"
            )
        intrinsics_by_group[group] = cameras_by_id[camera_id]
    return intrinsics_by_group


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
        camera_intrinsics_by_group = None
        if layout.kind == "multi":
            camera_intrinsics_by_group = _camera_intrinsics_by_dimension_report_order(
                cameras_txt=cameras_txt,
                dimension_reports=dimension_reports,
            )
        return IntrinsicsSelection(
            source="user_cameras_file",
            camera_model=None,
            selected_images={},
            warnings=[
                "Mapped user cameras.txt cameras to camera folders by sorted camera ID and folder name."
            ]
            if camera_intrinsics_by_group
            else [],
            user_cameras_file=cameras_txt,
            camera_params=camera_params_from_cameras_txt(cameras_txt) if layout.kind == "single" else None,
            camera_intrinsics_by_group=camera_intrinsics_by_group,
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
