"""Deterministic held-out camera selection for patch eval datasets."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from reefs.patches.artefacts import SparseImage, read_sparse_scene_text


@dataclass(frozen=True)
class HoldoutSelection:
    """Train/test split for one patch."""

    patch_id: str
    train_images: list[str]
    holdout_images: list[str]
    axis: str
    test_every: int

    def as_dict(self) -> dict[str, object]:
        return {
            "patch_id": self.patch_id,
            "axis": self.axis,
            "holdout_fraction": 0.05,
            "train_images": self.train_images,
            "holdout_images": self.holdout_images,
            "train_count": len(self.train_images),
            "holdout_count": len(self.holdout_images),
            "test_every": self.test_every,
        }


def select_holdout(patch_dir: Path) -> HoldoutSelection:
    """Select 5% of internal cameras, evenly spaced along the dominant XY axis."""
    metadata = json.loads((patch_dir / "patch_metadata.json").read_text(encoding="utf-8"))
    selected = [str(name) for name in metadata["selected_images"]]
    internal_count = int(metadata["selected_internal_count"])
    if internal_count <= 0:
        raise ValueError(f"patch has no internal cameras: {patch_dir}")
    internal_names = selected[:internal_count]
    scene = read_sparse_scene_text(patch_dir / "sparse" / "0")
    by_name = scene.image_by_name
    internal_images = [by_name[name] for name in internal_names if name in by_name]
    if not internal_images:
        raise ValueError(f"no internal images found in sparse model: {patch_dir}")

    xs = [image.center[0] for image in internal_images]
    ys = [image.center[1] for image in internal_images]
    x_span = max(xs) - min(xs)
    y_span = max(ys) - min(ys)
    axis = "x" if x_span >= y_span else "y"
    axis_index = 0 if axis == "x" else 1
    ordered = sorted(internal_images, key=lambda image: (image.center[axis_index], image.name))
    count = max(1, round(len(ordered) * 0.05))
    if count == 1:
        chosen = [ordered[len(ordered) // 2]]
    else:
        indexes = [round(i * (len(ordered) - 1) / (count - 1)) for i in range(count)]
        chosen = [ordered[index] for index in indexes]
    holdout = {image.name for image in chosen}
    train = [name for name in selected if name not in holdout]
    test_every = _test_every_for_count(total=len(selected), count=len(chosen))
    return HoldoutSelection(
        patch_id=str(metadata["patch_id"]),
        train_images=train,
        holdout_images=[image.name for image in chosen],
        axis=axis,
        test_every=test_every,
    )


def write_holdout_manifest(patch_dir: Path, output_path: Path) -> HoldoutSelection:
    """Write the holdout manifest for one patch."""
    selection = select_holdout(patch_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(selection.as_dict(), indent=2) + "\n", encoding="utf-8")
    return selection


def build_eval_dataset(*, patch_dir: Path, output_dir: Path, holdout: HoldoutSelection) -> None:
    """Create an LFS dataset with stable train/test order for --test-every."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
    images_dir = output_dir / "images"
    sparse_dir = output_dir / "sparse" / "0"
    images_dir.mkdir(parents=True)
    sparse_dir.mkdir(parents=True)
    for path in (patch_dir / "selected_images").rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(patch_dir / "selected_images")
        target = images_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(path.resolve())
    for name in ["cameras.txt", "points3D.txt"]:
        (sparse_dir / name).symlink_to((patch_dir / "sparse" / "0" / name).resolve())
    _write_reordered_images_txt(
        source=patch_dir / "sparse" / "0" / "images.txt",
        destination=sparse_dir / "images.txt",
        holdout_names=set(holdout.holdout_images),
        test_every=holdout.test_every,
    )


def _write_reordered_images_txt(
    *,
    source: Path,
    destination: Path,
    holdout_names: set[str],
    test_every: int,
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
    by_name = {name: (line, points) for name, line, points in records}
    holdout = [name for name, _, _ in records if name in holdout_names]
    train = [name for name, _, _ in records if name not in holdout_names]
    ordered: list[str] = []
    holdout_iter = iter(holdout)
    for name in train:
        if (len(ordered) + 1) % test_every == 0:
            chosen = next(holdout_iter, None)
            if chosen is not None:
                ordered.append(chosen)
        ordered.append(name)
    ordered.extend(list(holdout_iter))
    with destination.open("w", encoding="utf-8") as handle:
        handle.writelines(comments)
        for name in ordered:
            line, points = by_name[name]
            handle.write(line)
            handle.write(points)


def _test_every_for_count(*, total: int, count: int) -> int:
    """Return LFS --test-every N for exactly count validation images."""
    if count <= 0:
        raise ValueError("holdout count must be positive")
    if count == 1:
        return total + 1
    # LFS includes image index 0, then every Nth image.
    return max(2, (total - 1) // (count - 1))
