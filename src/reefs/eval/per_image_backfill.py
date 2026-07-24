"""Historical per-image scoring and deterministic extreme exports."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path, PurePosixPath

from reefs.eval.image_metrics import compute_per_image_metrics
from reefs.eval.lpips import load_lfs_comparison_images


SCORE_FIELDS = [
    "dataset_id",
    "dataset",
    "outer_run_id",
    "probe_run_id",
    "patch_id",
    "attempt",
    "iteration",
    "comparison_index",
    "image_name",
    "gt_width",
    "gt_height",
    "render_width",
    "render_height",
    "lpips",
    "psnr",
    "ssim",
    "metric_source",
    "target_image_source",
    "source_comparison_path",
    "source_comparison_sha256",
    "eval_manifest_sha256",
    "git_commit",
    "container_digest",
    "status",
    "failure_reason",
]


def comparison_image_names(
    *,
    comparison_dir: Path,
    eval_images_txt: Path,
    manifest_path: Path,
) -> dict[int, str]:
    """Map numeric comparison indices through reordered eval sparse positions."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    test_every = int(manifest["test_every"])
    sparse_names = _colmap_image_names(eval_images_txt)
    selected = [name for index, name in enumerate(sparse_names) if index % test_every == 0]
    holdouts = [str(PurePosixPath(name)) for name in manifest["holdout_images"]]
    if set(selected) != set(holdouts) or len(selected) != len(holdouts):
        raise ValueError("eval sparse --test-every selection does not match manifest holdout images")
    paths = list(comparison_dir.glob("*.png"))
    try:
        indices = sorted(int(path.stem) for path in paths)
    except ValueError as exc:
        raise ValueError("comparison filenames must be numeric PNG indices") from exc
    if indices != list(range(len(selected))):
        raise ValueError(f"comparison indices are not contiguous from zero: {indices}")
    return dict(zip(indices, selected, strict=True))


def score_patch(
    *,
    patch_dir: Path,
    output_csv: Path,
    provenance: dict[str, str],
) -> list[dict[str, object]]:
    """Score one immutable downloaded patch and write full provenance rows."""
    manifest_path = patch_dir / "eval_dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("target_image_source") != "full_resolution_undistorted":
        raise ValueError(f"patch is not full-resolution undistorted evaluation: {patch_dir}")
    comparison_dir = patch_dir / "eval_step_30000"
    names = comparison_image_names(
        comparison_dir=comparison_dir,
        eval_images_txt=patch_dir / "eval_sparse" / "images.txt",
        manifest_path=manifest_path,
    )
    metric_rows = compute_per_image_metrics(
        output_dir=patch_dir,
        iterations=[30_000],
        compute_lpips=True,
        expected_sizes={
            (int(size["width"]), int(size["height"]))
            for size in manifest["holdout_image_dimensions"].values()
        },
        metric_source="python_full_resolution_undistorted",
    )
    manifest_sha = sha256_file(manifest_path)
    rows: list[dict[str, object]] = []
    for metric in metric_rows:
        index = int(str(metric["comparison_index"]))
        comparison_path = comparison_dir / f"{index}.png"
        row: dict[str, object] = {
            **{field: provenance.get(field, "") for field in SCORE_FIELDS},
            **metric,
            "iteration": 30_000,
            "comparison_index": index,
            "image_name": names[index],
            "target_image_source": "full_resolution_undistorted",
            "source_comparison_path": _delivery_relative(comparison_path),
            "source_comparison_sha256": sha256_file(comparison_path),
            "eval_manifest_sha256": manifest_sha,
            "status": "complete",
            "failure_reason": "",
        }
        _validate_metrics(row)
        rows.append(row)
    _write_csv(output_csv, SCORE_FIELDS, rows)
    return rows


def export_extremes(*, score_csv: Path, patch_dir: Path, output_dir: Path) -> list[dict[str, object]]:
    """Export deterministic lowest/highest LPIPS images for one patch."""
    with score_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"score CSV has no rows: {score_csv}")
    best = sorted(rows, key=lambda row: (float(row["lpips"]), row["image_name"]))[:3]
    worst = sorted(rows, key=lambda row: (-float(row["lpips"]), row["image_name"]))[:3]
    selected: list[dict[str, object]] = []
    by_identity: dict[tuple[str, str], dict[str, object]] = {}
    for label, ranked in (("best", best), ("worst", worst)):
        target_dir = output_dir / label
        target_dir.mkdir(parents=True, exist_ok=True)
        for rank, row in enumerate(ranked, start=1):
            identity = (row["comparison_index"], row["image_name"])
            if identity in by_identity:
                existing = by_identity[identity]
                existing["class"] = "best_and_worst"
                existing["worst_rank"] = rank
                existing["overlap_reason"] = "patch_has_fewer_than_six_unique_images"
                continue
            comparison = patch_dir / "eval_step_30000" / f"{row['comparison_index']}.png"
            gt, rendered = load_lfs_comparison_images(comparison)
            safe_name = _safe_name(row["image_name"])
            stem = f"rank_{rank}_{safe_name}"
            gt_path = target_dir / f"{stem}_gt.png"
            render_path = target_dir / f"{stem}_render.png"
            comparison_path = target_dir / f"{stem}_comparison.png"
            _save_png(gt, gt_path)
            _save_png(rendered, render_path)
            shutil.copy2(comparison, comparison_path)
            selection: dict[str, object] = {
                    "class": label,
                    "rank": rank,
                    "best_rank": rank if label == "best" else "",
                    "worst_rank": rank if label == "worst" else "",
                    "overlap_reason": "",
                    **row,
                    "gt_path": gt_path.as_posix(),
                    "gt_sha256": sha256_file(gt_path),
                    "render_path": render_path.as_posix(),
                    "render_sha256": sha256_file(render_path),
                    "comparison_path": comparison_path.as_posix(),
                    "comparison_sha256": sha256_file(comparison_path),
                }
            selected.append(selection)
            by_identity[identity] = selection
    fields = list(selected[0]) if selected else []
    _write_csv(output_dir / "selection.csv", fields, selected)
    return selected


def combine_score_csvs(*, inputs: list[Path], output_csv: Path) -> list[dict[str, object]]:
    """Combine validated score CSVs without changing their schema or order."""
    rows: list[dict[str, object]] = []
    for path in inputs:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != SCORE_FIELDS:
                raise ValueError(f"unexpected score CSV schema: {path}")
            rows.extend(reader)
    identities = [(row["dataset"], row["patch_id"], row["comparison_index"]) for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("combined score CSV contains duplicate dataset/patch/index rows")
    _write_csv(output_csv, SCORE_FIELDS, rows)
    return rows


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _colmap_image_names(path: Path) -> list[str]:
    names: list[str] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        while True:
            line = handle.readline()
            if not line:
                break
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            points = handle.readline()
            if not points and not handle.closed:
                raise ValueError(f"COLMAP image record has no observation line: {path}")
            parts = stripped.split(maxsplit=9)
            if len(parts) != 10:
                raise ValueError(f"malformed COLMAP image record: {stripped}")
            names.append(str(PurePosixPath(parts[9])))
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate image names in eval sparse model: {path}")
    return names


def _validate_metrics(row: dict[str, object]) -> None:
    for name in ("lpips", "ssim"):
        if not math.isfinite(float(row[name])):
            raise ValueError(f"non-finite {name} for comparison {row['comparison_index']}")
    psnr = float(row["psnr"])
    if math.isnan(psnr) or psnr == -math.inf:
        raise ValueError(f"invalid PSNR for comparison {row['comparison_index']}")


def _safe_name(name: str) -> str:
    flattened = "__".join(PurePosixPath(name).parts)
    return "".join(character if character.isalnum() or character in "._-" else "_" for character in flattened)


def _delivery_relative(path: Path) -> str:
    parts = path.parts
    if "patch-results" in parts:
        return Path(*parts[parts.index("patch-results") + 1 :]).as_posix()
    return path.as_posix()


def _save_png(image, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    image.save(tmp, format="PNG", compress_level=1)
    tmp.replace(path)


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)
