"""Deterministic holdout handling for LFS eval datasets."""

from __future__ import annotations

import json
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from reefs.patches.artefacts import SparseCamera, read_image_names_text, read_sparse_scene_text


@dataclass(frozen=True)
class HoldoutSelection:
    """A stable train/holdout split for one patch."""

    patch_id: str
    holdout_images: list[str]
    train_images: list[str]
    requested_holdout_images: list[str]
    missing_holdout_images: list[str]
    test_every: int
    selected_image_count: int
    image_set_hash: str

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable split."""
        return {
            "patch_id": self.patch_id,
            "holdout_images": self.holdout_images,
            "train_images": self.train_images,
            "requested_holdout_images": self.requested_holdout_images,
            "missing_holdout_images": self.missing_holdout_images,
            "holdout_count": len(self.holdout_images),
            "train_count": len(self.train_images),
            "missing_holdout_count": len(self.missing_holdout_images),
            "test_every": self.test_every,
            "selected_image_count": self.selected_image_count,
            "image_set_hash": self.image_set_hash,
        }


def load_or_create_holdout(
    *,
    patch_dir: Path,
    canonical_path: Path,
    holdout_fraction: float,
) -> HoldoutSelection:
    """Reuse a canonical holdout or create it from the current patch."""
    requested: list[str] | None = None
    expected_hash: str | None = None
    if canonical_path.exists():
        data = json.loads(canonical_path.read_text(encoding="utf-8"))
        requested = [str(name) for name in data.get("requested_holdout_images") or data.get("holdout_images") or []]
        expected_hash = str(data.get("image_set_hash") or "")
    selection = select_holdout(patch_dir=patch_dir, holdout_fraction=holdout_fraction, requested_holdout=requested)
    if canonical_path.exists():
        if expected_hash and expected_hash != selection.image_set_hash:
            raise ValueError(
                f"canonical holdout image set does not match current patch: {canonical_path} "
                f"({expected_hash} != {selection.image_set_hash})"
            )
        return selection
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_path.write_text(json.dumps(selection.as_dict(), indent=2) + "\n", encoding="utf-8")
    return selection


def select_holdout(
    *,
    patch_dir: Path,
    holdout_fraction: float,
    requested_holdout: list[str] | None = None,
) -> HoldoutSelection:
    """Select a deterministic holdout from internal registered patch cameras."""
    metadata = json.loads((patch_dir / "patch_metadata.json").read_text(encoding="utf-8"))
    patch_id = str(metadata["patch_id"])
    selected = [str(name) for name in metadata["selected_images"]]
    image_set_hash = _image_set_hash(selected)
    internal_count = int(metadata["selected_internal_count"])
    internal_names = selected[:internal_count]
    if requested_holdout is not None:
        registered = set(read_image_names_text(patch_dir / "sparse" / "0" / "images.txt"))
        available = set(internal_names) & registered
        if not available:
            raise ValueError(f"patch has no registered internal images: {patch_dir}")
        holdout_names = [name for name in requested_holdout if name in available]
        missing = [name for name in requested_holdout if name not in available]
        if not holdout_names:
            raise ValueError(f"requested holdout has no registered internal images: {patch_dir}")
    else:
        scene = read_sparse_scene_text(patch_dir / "sparse" / "0")
        by_name = scene.image_by_name
        internal_images = [by_name[name] for name in internal_names if name in by_name]
        if not internal_images:
            raise ValueError(f"patch has no registered internal images: {patch_dir}")
        holdout_names = _new_holdout_names(internal_images, selected_count=len(selected), holdout_fraction=holdout_fraction)
        missing = []
    holdout_names = _fit_lfs_expressible_count(selected=selected, holdout_names=holdout_names)
    holdout = set(holdout_names)
    test_every = test_every_for_count(total=len(selected), count=len(holdout_names))
    return HoldoutSelection(
        patch_id=patch_id,
        holdout_images=holdout_names,
        train_images=[name for name in selected if name not in holdout],
        requested_holdout_images=requested_holdout or holdout_names,
        missing_holdout_images=missing,
        test_every=test_every,
        selected_image_count=len(selected),
        image_set_hash=image_set_hash,
    )


def _image_set_hash(selected_images: list[str]) -> str:
    """Return a stable hash for the ordered patch image set."""
    digest = hashlib.sha256()
    for name in selected_images:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def build_eval_dataset(
    *,
    patch_dir: Path,
    output_dir: Path,
    holdout: HoldoutSelection,
    target_image_source: str = "training_undistorted",
    source_images_dir: Path | None = None,
) -> None:
    """Create an eval dataset whose image order matches LFS --test-every."""
    target_image_source = normalise_target_image_source(target_image_source)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    image_source = source_images_dir or patch_dir / "selected_images"
    selected_images = _selected_images(patch_dir)
    missing_images = [name for name in selected_images if not (image_source / name).is_file()]
    if missing_images:
        raise ValueError(
            f"eval image source is missing {len(missing_images)} selected image(s) for {patch_dir}: "
            + ", ".join(missing_images[:5])
        )
    images_dir = output_dir / "images"
    sparse_dir = output_dir / "sparse" / "0"
    images_dir.mkdir(parents=True)
    sparse_dir.mkdir(parents=True)
    for name in selected_images:
        target = images_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to((image_source / name).resolve())
    source_sparse = patch_dir / "sparse" / "0"
    if target_image_source == "full_resolution_undistorted":
        geometry = _write_scaled_sparse_for_full_res_eval(
            source_sparse=source_sparse,
            destination=sparse_dir,
            image_source=image_source,
            selected_images=selected_images,
            holdout_names=set(holdout.holdout_images),
            test_every=holdout.test_every,
        )
    else:
        geometry = {"mode": "patch_sparse", "camera_scales": {}}
        (sparse_dir / "cameras.txt").symlink_to((source_sparse / "cameras.txt").resolve())
        _write_reordered_images_txt(
            source=source_sparse / "images.txt",
            destination=sparse_dir / "images.txt",
            holdout_names=set(holdout.holdout_images),
            test_every=holdout.test_every,
        )
    (sparse_dir / "points3D.txt").symlink_to((source_sparse / "points3D.txt").resolve())
    dimensions = _image_dimensions(images_dir=images_dir, names=holdout.holdout_images)
    manifest = {
        "target_image_source": target_image_source,
        "camera_source": str(source_sparse),
        "eval_sparse": str(sparse_dir),
        "image_source": str(image_source),
        "uses_patch_training_images": source_images_dir is None,
        "is_full_resolution_eval": target_image_source == "full_resolution_undistorted",
        "resize_or_crop_policy": (
            "uses full-resolution undistorted images at their native size; patch sparse pinhole "
            "intrinsics and observations are scaled to the target image dimensions"
            if target_image_source == "full_resolution_undistorted"
            else "uses patch selected_images exactly as produced by SfM undistortion"
        ),
        "geometry_policy": geometry,
        "metric_implementation": (
            "Python PSNR/SSIM/LPIPS from saved held-out LFS GT/render comparison images; "
            "LFS metric CSV output is discarded"
        ),
        "metric_source": f"python_{target_image_source}",
        "patch_id": holdout.patch_id,
        "selected_image_count": holdout.selected_image_count,
        "holdout_image_count": len(holdout.holdout_images),
        "image_set_hash": holdout.image_set_hash,
        "holdout_image_dimensions": dimensions,
        "holdout_images": holdout.holdout_images,
        "train_images": holdout.train_images,
        "test_every": holdout.test_every,
    }
    (output_dir / "eval_dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def normalise_target_image_source(source: str) -> str:
    """Return the canonical eval target label for patch-training undistorted images."""
    if source in {"patch_undistorted", "resized_undistorted"}:
        return "training_undistorted"
    return source


def _write_scaled_sparse_for_full_res_eval(
    *,
    source_sparse: Path,
    destination: Path,
    image_source: Path,
    selected_images: list[str],
    holdout_names: set[str],
    test_every: int,
) -> dict[str, object]:
    """Write an eval sparse model whose pinhole cameras match full-res targets."""
    scene = read_sparse_scene_text(source_sparse)
    image_sizes = _target_image_sizes(images_dir=image_source, names=selected_images)
    scales_by_camera = _camera_scales_for_targets(scene=scene, image_sizes=image_sizes)
    _write_scaled_cameras_txt(
        source=source_sparse / "cameras.txt",
        destination=destination / "cameras.txt",
        scene_cameras=scene.cameras,
        scales_by_camera=scales_by_camera,
    )
    _write_reordered_images_txt(
        source=source_sparse / "images.txt",
        destination=destination / "images.txt",
        holdout_names=holdout_names,
        test_every=test_every,
        scales_by_image={
            image.name: scales_by_camera[image.camera_id]
            for image in scene.images
            if image.camera_id in scales_by_camera
        },
    )
    return {
        "mode": "scaled_patch_sparse",
        "source_sparse": str(source_sparse),
        "camera_scales": {
            str(camera_id): {
                "scale_x": scale[0],
                "scale_y": scale[1],
                "target_width": size[0],
                "target_height": size[1],
            }
            for camera_id, (scale, size) in _camera_scale_summary(
                scene_cameras=scene.cameras,
                scales_by_camera=scales_by_camera,
            ).items()
        },
    }


def _target_image_sizes(*, images_dir: Path, names: list[str]) -> dict[str, tuple[int, int]]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("Pillow is required to validate full-resolution eval image geometry") from exc
    sizes: dict[str, tuple[int, int]] = {}
    for name in names:
        with Image.open(images_dir / name) as image:
            sizes[name] = image.size
    return sizes


def _camera_scales_for_targets(*, scene, image_sizes: dict[str, tuple[int, int]]) -> dict[int, tuple[float, float]]:
    scales: dict[int, tuple[float, float]] = {}
    target_sizes: dict[int, tuple[int, int]] = {}
    for image in scene.images:
        if image.name not in image_sizes:
            continue
        camera = scene.cameras.get(image.camera_id)
        if camera is None or camera.width <= 0 or camera.height <= 0:
            raise ValueError(f"cannot scale full-resolution eval camera {image.camera_id}: missing source dimensions")
        target_width, target_height = image_sizes[image.name]
        if target_width <= 0 or target_height <= 0:
            raise ValueError(f"invalid full-resolution eval target dimensions for {image.name}: {target_width}x{target_height}")
        existing_target = target_sizes.setdefault(image.camera_id, (target_width, target_height))
        if existing_target != (target_width, target_height):
            raise ValueError(
                f"full-resolution eval camera {image.camera_id} maps to multiple target sizes: "
                f"{existing_target} and {(target_width, target_height)}"
            )
        scales[image.camera_id] = (target_width / camera.width, target_height / camera.height)
    if not scales:
        raise ValueError("full-resolution eval sparse model has no cameras to scale")
    return scales


def _camera_scale_summary(
    *,
    scene_cameras: dict[int, SparseCamera],
    scales_by_camera: dict[int, tuple[float, float]],
) -> dict[int, tuple[tuple[float, float], tuple[int, int]]]:
    summary = {}
    for camera_id, scale in scales_by_camera.items():
        camera = scene_cameras[camera_id]
        summary[camera_id] = (scale, (round(camera.width * scale[0]), round(camera.height * scale[1])))
    return summary


def _write_scaled_cameras_txt(
    *,
    source: Path,
    destination: Path,
    scene_cameras: dict[int, SparseCamera],
    scales_by_camera: dict[int, tuple[float, float]],
) -> None:
    with source.open("r", encoding="utf-8", errors="replace") as handle, destination.open("w", encoding="utf-8") as out:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                out.write(line)
                continue
            parts = stripped.split()
            camera_id = int(parts[0])
            if camera_id not in scales_by_camera:
                out.write(line)
                continue
            camera = scene_cameras[camera_id]
            scale_x, scale_y = scales_by_camera[camera_id]
            width = round(camera.width * scale_x)
            height = round(camera.height * scale_y)
            params = _scaled_camera_params(camera, scale_x=scale_x, scale_y=scale_y)
            out.write(
                f"{camera.camera_id} {camera.model} {width} {height} "
                + " ".join(_format_float(value) for value in params)
                + "\n"
            )


def _scaled_camera_params(camera: SparseCamera, *, scale_x: float, scale_y: float) -> tuple[float, ...]:
    model = camera.model.upper()
    params = camera.params
    if model == "PINHOLE" and len(params) == 4:
        fx, fy, cx, cy = params
        return fx * scale_x, fy * scale_y, cx * scale_x, cy * scale_y
    if model == "SIMPLE_PINHOLE" and len(params) == 3:
        if abs(scale_x - scale_y) > 1e-6:
            raise ValueError("cannot scale SIMPLE_PINHOLE camera with non-uniform full-resolution target dimensions")
        f, cx, cy = params
        return f * scale_x, cx * scale_x, cy * scale_y
    raise ValueError(f"full-resolution eval supports PINHOLE/SIMPLE_PINHOLE sparse cameras, not {camera.model}")


def _selected_images(patch_dir: Path) -> list[str]:
    metadata = json.loads((patch_dir / "patch_metadata.json").read_text(encoding="utf-8"))
    return [str(name) for name in metadata["selected_images"]]


def _image_dimensions(*, images_dir: Path, names: list[str]) -> dict[str, dict[str, int | str]]:
    """Return best-effort image dimensions for an eval manifest."""
    try:
        from PIL import Image
    except ImportError:
        return {name: {"error": "pillow_unavailable"} for name in names}
    dimensions: dict[str, dict[str, int | str]] = {}
    for name in names:
        try:
            with Image.open(images_dir / name) as image:
                width, height = image.size
            dimensions[name] = {"width": width, "height": height}
        except OSError as exc:
            dimensions[name] = {"error": str(exc)}
    return dimensions


def test_every_for_count(*, total: int, count: int) -> int:
    """Return an LFS --test-every value that selects count images."""
    if count <= 0:
        raise ValueError("holdout count must be positive")
    for value in range(2, total + 2):
        if (total - 1) // value + 1 == count:
            return value
    raise ValueError(f"cannot express {count}/{total} holdout images with LFS --test-every")


def _new_holdout_names(internal_images, *, selected_count: int, holdout_fraction: float) -> list[str]:
    xs = [image.center[0] for image in internal_images]
    ys = [image.center[1] for image in internal_images]
    axis_index = 0 if max(xs) - min(xs) >= max(ys) - min(ys) else 1
    ordered = sorted(internal_images, key=lambda image: (image.center[axis_index], image.name))
    target = max(1, round(selected_count * holdout_fraction))
    count = _nearest_expressible_count(total=selected_count, target=target, max_count=len(ordered), allow_above=True)
    if count == 1:
        return [ordered[len(ordered) // 2].name]
    indexes = [round(index * (len(ordered) - 1) / (count - 1)) for index in range(count)]
    return [ordered[index].name for index in indexes]


def _fit_lfs_expressible_count(*, selected: list[str], holdout_names: list[str]) -> list[str]:
    count = _nearest_expressible_count(
        total=len(selected),
        target=len(holdout_names),
        max_count=len(holdout_names),
        allow_above=False,
    )
    if count == len(holdout_names):
        return holdout_names
    if count == 1:
        return [holdout_names[len(holdout_names) // 2]]
    indexes = [round(index * (len(holdout_names) - 1) / (count - 1)) for index in range(count)]
    return [holdout_names[index] for index in indexes]


def _nearest_expressible_count(*, total: int, target: int, max_count: int, allow_above: bool) -> int:
    possible = {
        (total - 1) // test_every + 1
        for test_every in range(2, total + 2)
        if (total - 1) // test_every + 1 <= max_count
    }
    if not allow_above:
        possible = {count for count in possible if count <= target}
    if not possible:
        raise ValueError(f"cannot express a holdout for {total} images")
    return min(possible, key=lambda count: (abs(count - target), count > target, -count))


def _write_reordered_images_txt(
    *,
    source: Path,
    destination: Path,
    holdout_names: set[str],
    test_every: int,
    scales_by_image: dict[str, tuple[float, float]] | None = None,
) -> None:
    comments: list[str] = []
    records: list[tuple[str, str, str]] = []
    with source.open("r", encoding="utf-8", errors="replace") as handle:
        while True:
            line = handle.readline()
            if not line:
                break
            if not line.strip() or line.lstrip().startswith("#"):
                comments.append(line)
                continue
            points = handle.readline()
            name = line.strip().split(maxsplit=9)[9]
            records.append((name, line, points))
    holdout = [name for name, _, _ in records if name in holdout_names]
    train = [name for name, _, _ in records if name not in holdout_names]
    slots = [index for index in range(len(records)) if index % test_every == 0]
    if len(slots) != len(holdout):
        raise ValueError(f"LFS --test-every={test_every} selects {len(slots)} images, not {len(holdout)}")
    by_name = {name: (line, points) for name, line, points in records}
    ordered: list[str | None] = [None] * len(records)
    holdout_iter = iter(holdout)
    for index in slots:
        ordered[index] = next(holdout_iter)
    train_iter = iter(train)
    for index, name in enumerate(ordered):
        if name is None:
            ordered[index] = next(train_iter)
    with destination.open("w", encoding="utf-8") as handle:
        handle.writelines(comments)
        for name in ordered:
            assert name is not None
            image_line, point_line = by_name[name]
            handle.write(image_line)
            if scales_by_image and name in scales_by_image:
                handle.write(_scaled_points_line(point_line, scales_by_image[name]))
            else:
                handle.write(point_line)


def _scaled_points_line(line: str, scale: tuple[float, float]) -> str:
    tokens = line.split()
    if not tokens:
        return line
    scale_x, scale_y = scale
    scaled: list[str] = []
    for index in range(0, len(tokens), 3):
        try:
            x = float(tokens[index]) * scale_x
            y = float(tokens[index + 1]) * scale_y
            point_id = tokens[index + 2]
        except (IndexError, ValueError):
            return line
        scaled.extend([_format_float(x), _format_float(y), point_id])
    return " ".join(scaled) + "\n"


def _format_float(value: float) -> str:
    return f"{value:.12g}"
