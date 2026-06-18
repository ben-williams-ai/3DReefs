"""Patch metadata and COLMAP sparse artefact helpers."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from reefs.colmap.outputs import SparseModelSummary, summarise_sparse_model


SPARSE_BASENAMES = ("cameras", "images", "points3D")


@dataclass(frozen=True)
class SparseModelFiles:
    """Detected files for a COLMAP sparse model."""

    path: Path
    cameras: Path
    images: Path
    points3d: Path
    format: str
    summary: SparseModelSummary

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable model-file summary."""
        return {
            "path": str(self.path),
            "format": self.format,
            "cameras": str(self.cameras),
            "images": str(self.images),
            "points3d": str(self.points3d),
            "summary": self.summary.as_dict(),
        }


@dataclass(frozen=True)
class SparseCamera:
    """COLMAP camera intrinsics from a text sparse model."""

    camera_id: int
    model: str
    width: int
    height: int
    params: tuple[float, ...]


@dataclass(frozen=True)
class SparseObservation:
    """One 2D COLMAP observation from an image points line."""

    x: float
    y: float
    point3d_id: int


@dataclass(frozen=True)
class SparseImage:
    """Registered image pose and name from a COLMAP text model."""

    image_id: int
    camera_id: int
    name: str
    qvec: tuple[float, float, float, float]
    tvec: tuple[float, float, float]
    center: tuple[float, float, float]
    header_line: str
    points_line: str
    width: int = 0
    height: int = 0
    observations: tuple[SparseObservation, ...] = ()


@dataclass(frozen=True)
class SparsePoint:
    """Sparse 3D point and visible image ids from a COLMAP text model."""

    point_id: int
    xyz: tuple[float, float, float]
    track_image_ids: tuple[int, ...]
    line: str
    track_point2d_idxs: tuple[int, ...] = ()

    @property
    def track_pairs(self) -> tuple[tuple[int, int], ...]:
        """Return `(image_id, point2D_idx)` track pairs."""
        if len(self.track_image_ids) != len(self.track_point2d_idxs):
            return tuple((image_id, 0) for image_id in self.track_image_ids)
        return tuple(zip(self.track_image_ids, self.track_point2d_idxs, strict=True))


@dataclass(frozen=True)
class SparseScene:
    """Parsed COLMAP text sparse scene used for patch planning."""

    model_dir: Path
    cameras_text: str
    images: list[SparseImage]
    points: list[SparsePoint]
    cameras: dict[int, SparseCamera] = field(default_factory=dict)

    @property
    def image_by_id(self) -> dict[int, SparseImage]:
        """Return images keyed by COLMAP image id."""
        return {image.image_id: image for image in self.images}

    @property
    def image_by_name(self) -> dict[str, SparseImage]:
        """Return images keyed by relative image name."""
        return {image.name: image for image in self.images}


def _quaternion_to_rotation_matrix(qvec: tuple[float, float, float, float]) -> tuple[tuple[float, float, float], ...]:
    qw, qx, qy, qz = qvec
    return (
        (
            1.0 - 2.0 * qy * qy - 2.0 * qz * qz,
            2.0 * qx * qy - 2.0 * qz * qw,
            2.0 * qx * qz + 2.0 * qy * qw,
        ),
        (
            2.0 * qx * qy + 2.0 * qz * qw,
            1.0 - 2.0 * qx * qx - 2.0 * qz * qz,
            2.0 * qy * qz - 2.0 * qx * qw,
        ),
        (
            2.0 * qx * qz - 2.0 * qy * qw,
            2.0 * qy * qz + 2.0 * qx * qw,
            1.0 - 2.0 * qx * qx - 2.0 * qy * qy,
        ),
    )


def _projection_center(
    qvec: tuple[float, float, float, float],
    tvec: tuple[float, float, float],
) -> tuple[float, float, float]:
    rotation = _quaternion_to_rotation_matrix(qvec)
    return tuple(
        -sum(rotation[row][axis] * tvec[row] for row in range(3))
        for axis in range(3)
    )


def _existing_sparse_file(model_dir: Path, basename: str) -> tuple[Path, str] | None:
    for suffix, file_format in [(".txt", "text"), (".bin", "binary")]:
        path = model_dir / f"{basename}{suffix}"
        if path.exists():
            return path, file_format
    return None


def detect_sparse_model_files(model_dir: Path) -> SparseModelFiles:
    """Validate and describe a COLMAP sparse model directory."""
    if not model_dir.exists():
        raise ValueError(f"Sparse model directory does not exist: {model_dir}")
    detected = {basename: _existing_sparse_file(model_dir, basename) for basename in SPARSE_BASENAMES}
    missing = [basename for basename, value in detected.items() if value is None]
    if missing:
        raise ValueError(
            "Sparse model is missing required COLMAP files "
            f"{', '.join(missing)} under {model_dir}"
        )
    formats = {value[1] for value in detected.values() if value is not None}
    file_format = "mixed" if len(formats) > 1 else next(iter(formats))
    return SparseModelFiles(
        path=model_dir,
        cameras=detected["cameras"][0],  # type: ignore[index]
        images=detected["images"][0],  # type: ignore[index]
        points3d=detected["points3D"][0],  # type: ignore[index]
        format=file_format,
        summary=summarise_sparse_model(model_dir),
    )


def has_text_sparse_model(model_dir: Path) -> bool:
    """Return whether a sparse model has all required text files."""
    return all((model_dir / f"{basename}.txt").exists() for basename in SPARSE_BASENAMES)


def ensure_text_sparse_model(model_dir: Path, text_dir: Path) -> Path:
    """Return a COLMAP text sparse model, exporting from binary when needed."""
    if has_text_sparse_model(model_dir):
        return model_dir
    if text_dir.exists():
        shutil.rmtree(text_dir)
    text_dir.mkdir(parents=True, exist_ok=True)
    try:
        import pycolmap

        reconstruction = pycolmap.Reconstruction(str(model_dir))
        reconstruction.write_text(str(text_dir))
    except Exception as exc:
        raise ValueError(
            "Patch generation requires COLMAP text sparse files or a pycolmap-readable "
            f"binary sparse model. Failed to export {model_dir} to text: {exc}"
        ) from exc
    detect_sparse_model_files(text_dir)
    return text_dir


def read_image_names_text(images_txt: Path) -> list[str]:
    """Read registered image names from COLMAP `images.txt`."""
    names: list[str] = []
    if not images_txt.exists():
        return names
    pattern = re.compile(
        r"^\s*\d+\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s+[-+0-9.eE]+"
        r"\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s+\d+\s+(.+?)\s*$"
    )
    with images_txt.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = pattern.match(stripped)
            if match:
                names.append(match.group(1))
    return names


def read_sparse_scene_text(model_dir: Path) -> SparseScene:
    """Read the subset of COLMAP text model data needed by patching."""
    cameras_txt = model_dir / "cameras.txt"
    images_txt = model_dir / "images.txt"
    points_txt = model_dir / "points3D.txt"
    if not (cameras_txt.exists() and images_txt.exists() and points_txt.exists()):
        raise ValueError(f"Patch generation currently requires COLMAP text sparse files under {model_dir}")

    cameras: dict[int, SparseCamera] = {}
    with cameras_txt.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) < 4:
                continue
            try:
                camera_id = int(parts[0])
                cameras[camera_id] = SparseCamera(
                    camera_id=camera_id,
                    model=parts[1],
                    width=int(parts[2]),
                    height=int(parts[3]),
                    params=tuple(float(value) for value in parts[4:]),
                )
            except (IndexError, ValueError):
                continue

    images: list[SparseImage] = []
    with images_txt.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split(maxsplit=9)
            if len(parts) < 10:
                continue
            try:
                image_id = int(parts[0])
                qvec = tuple(float(value) for value in parts[1:5])
                tvec = tuple(float(value) for value in parts[5:8])
                camera_id = int(parts[8])
            except ValueError:
                continue
            raw_points_line = next(handle, "")
            points_line = raw_points_line.rstrip("\n")
            observation_tokens = points_line.split()
            observations: list[SparseObservation] = []
            for obs_index in range(0, len(observation_tokens), 3):
                try:
                    observations.append(
                        SparseObservation(
                            x=float(observation_tokens[obs_index]),
                            y=float(observation_tokens[obs_index + 1]),
                            point3d_id=int(observation_tokens[obs_index + 2]),
                        )
                    )
                except (IndexError, ValueError):
                    continue
            camera = cameras.get(camera_id)
            width, height = (camera.width, camera.height) if camera else (0, 0)
            images.append(
                SparseImage(
                    image_id=image_id,
                    camera_id=camera_id,
                    name=parts[9],
                    qvec=qvec,  # type: ignore[arg-type]
                    tvec=tvec,  # type: ignore[arg-type]
                    center=_projection_center(qvec, tvec),  # type: ignore[arg-type]
                    header_line=line,
                    points_line=points_line,
                    width=width,
                    height=height,
                    observations=tuple(observations),
                )
            )

    points: list[SparsePoint] = []
    with points_txt.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) < 8:
                continue
            try:
                point_id = int(parts[0])
                xyz = (float(parts[1]), float(parts[2]), float(parts[3]))
                track_tokens = parts[8:]
                track_image_ids = tuple(int(track_tokens[i]) for i in range(0, len(track_tokens), 2))
                track_point2d_idxs = tuple(int(track_tokens[i + 1]) for i in range(0, len(track_tokens), 2))
            except ValueError:
                continue
            points.append(
                SparsePoint(
                    point_id=point_id,
                    xyz=xyz,
                    track_image_ids=track_image_ids,
                    track_point2d_idxs=track_point2d_idxs,
                    line=line,
                )
            )

    if not images:
        raise ValueError(f"No registered images found in COLMAP text model: {model_dir}")
    return SparseScene(
        model_dir=model_dir,
        cameras_text=cameras_txt.read_text(encoding="utf-8", errors="replace"),
        images=images,
        points=points,
        cameras=cameras,
    )
