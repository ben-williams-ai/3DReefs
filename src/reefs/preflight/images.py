"""Image layout validation for project directories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reefs.colour.ordering import IMAGE_SUFFIXES, camera_dirs, image_files, natural_key


@dataclass(frozen=True)
class ImageLayout:
    """Detected image layout."""

    kind: str
    image_paths: list[Path]
    camera_dirs: list[str]

    @property
    def relative_image_paths(self) -> list[Path]:
        """Return image paths relative to raw_images or camera dirs."""
        return self.image_paths


def _is_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES


def _direct_images(path: Path) -> list[Path]:
    return [p.name for p in image_files(path)]


def _camera_dirs(path: Path) -> list[Path]:
    return camera_dirs(path)


def detect_image_layout(raw_images: Path) -> ImageLayout:
    """Detect single-camera or multi-camera image organisation."""
    if not raw_images.exists() or not raw_images.is_dir():
        raise ValueError(f"raw_images directory does not exist: {raw_images}")

    direct = _direct_images(raw_images)
    camera_dirs = _camera_dirs(raw_images)
    camera_dirs_with_images = [d for d in camera_dirs if _direct_images(d)]

    if direct and camera_dirs:
        raise ValueError("raw_images mixes direct images and camera subfolders")
    if direct:
        return ImageLayout(kind="single", image_paths=[Path(name) for name in direct], camera_dirs=[])
    if camera_dirs_with_images:
        image_paths: list[Path] = []
        for camera_dir in camera_dirs_with_images:
            image_paths.extend(Path(camera_dir.name) / name for name in _direct_images(camera_dir))
        return ImageLayout(
            kind="multi",
            image_paths=sorted(image_paths, key=natural_key),
            camera_dirs=[p.name for p in camera_dirs_with_images],
        )
    raise ValueError(f"No supported image files found in {raw_images}")


def validate_recoloured_mirror(
    *, raw_images: Path, recoloured_images: Path, layout: ImageLayout
) -> None:
    """Validate recoloured_images mirrors raw image relative paths."""
    if not recoloured_images.exists() or not recoloured_images.is_dir():
        raise ValueError(f"recoloured_images directory does not exist: {recoloured_images}")

    expected = set(layout.relative_image_paths)
    actual: set[Path] = set()
    if layout.kind == "single":
        actual = {Path(name) for name in _direct_images(recoloured_images)}
    else:
        for camera_dir in _camera_dirs(recoloured_images):
            for name in _direct_images(camera_dir):
                actual.add(Path(camera_dir.name) / name)

    missing = sorted(expected - actual, key=natural_key)
    extra = sorted(actual - expected, key=natural_key)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing recoloured images: {', '.join(map(str, missing[:10]))}")
        if extra:
            details.append(f"extra recoloured images: {', '.join(map(str, extra[:10]))}")
        raise ValueError("; ".join(details))
