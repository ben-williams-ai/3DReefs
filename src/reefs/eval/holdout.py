"""Deterministic holdout handling for LFS eval datasets."""

from __future__ import annotations

import json
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from reefs.patches.artefacts import read_image_names_text, read_sparse_scene_text


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
    target_image_source: str = "resized_undistorted",
    source_images_dir: Path | None = None,
) -> None:
    """Create an eval dataset whose image order matches LFS --test-every."""
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
    for name in ["cameras.txt", "points3D.txt"]:
        (sparse_dir / name).symlink_to((patch_dir / "sparse" / "0" / name).resolve())
    _write_reordered_images_txt(
        source=patch_dir / "sparse" / "0" / "images.txt",
        destination=sparse_dir / "images.txt",
        holdout_names=set(holdout.holdout_images),
        test_every=holdout.test_every,
    )
    dimensions = _image_dimensions(images_dir=images_dir, names=holdout.holdout_images)
    manifest = {
        "target_image_source": target_image_source,
        "camera_source": str(patch_dir / "sparse" / "0"),
        "image_source": str(image_source),
        "uses_patch_training_images": source_images_dir is None,
        "is_full_resolution_eval": target_image_source == "full_resolution_undistorted",
        "resize_or_crop_policy": (
            "uses full-resolution undistorted images with the same relative names as the patch sparse model"
            if target_image_source == "full_resolution_undistorted"
            else "uses patch selected_images exactly as produced by SfM undistortion"
        ),
        "metric_implementation": "LichtFeld Studio metrics.csv",
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


def _write_reordered_images_txt(*, source: Path, destination: Path, holdout_names: set[str], test_every: int) -> None:
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
            handle.write(point_line)
