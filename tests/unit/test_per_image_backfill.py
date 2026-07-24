"""Tests for historical per-image mapping and exports."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from PIL import Image

from reefs.eval.per_image_backfill import comparison_image_names, export_extremes


def _images_txt(path: Path) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        "# images\n"
        "1 1 0 0 0 0 0 0 1 cam/a.jpg\n\n"
        "2 1 0 0 0 0 0 0 1 cam/train.jpg\n\n"
        "3 1 0 0 0 0 0 0 1 cam/b.jpg\n\n",
        encoding="utf-8",
    )


def test_comparison_mapping_uses_sparse_test_every_order(tmp_path: Path) -> None:
    comparisons = tmp_path / "eval_step_30000"
    comparisons.mkdir()
    for index in range(2):
        (comparisons / f"{index}.png").touch()
    images = tmp_path / "eval_sparse" / "images.txt"
    _images_txt(images)
    manifest = tmp_path / "eval_dataset_manifest.json"
    manifest.write_text(
        json.dumps({"test_every": 2, "holdout_images": ["cam/b.jpg", "cam/a.jpg"]}),
        encoding="utf-8",
    )

    assert comparison_image_names(
        comparison_dir=comparisons,
        eval_images_txt=images,
        manifest_path=manifest,
    ) == {0: "cam/a.jpg", 1: "cam/b.jpg"}


def test_comparison_mapping_rejects_missing_index(tmp_path: Path) -> None:
    comparisons = tmp_path / "eval_step_30000"
    comparisons.mkdir()
    (comparisons / "1.png").touch()
    images = tmp_path / "eval_sparse" / "images.txt"
    _images_txt(images)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"test_every": 2, "holdout_images": ["cam/a.jpg", "cam/b.jpg"]}))

    with pytest.raises(ValueError, match="contiguous"):
        comparison_image_names(comparison_dir=comparisons, eval_images_txt=images, manifest_path=manifest)


def test_export_extremes_ranks_lpips_and_splits_losslessly(tmp_path: Path) -> None:
    patch = tmp_path / "patch"
    comparisons = patch / "eval_step_30000"
    comparisons.mkdir(parents=True)
    rows = []
    for index, lpips in enumerate((0.3, 0.1, 0.2, 0.8, 0.9, 0.7)):
        composite = Image.new("RGB", (12, 4))
        composite.paste(Image.new("RGB", (4, 4), (index, 0, 0)), (0, 0))
        composite.paste(Image.new("RGB", (4, 4), (0, index, 0)), (8, 0))
        composite.save(comparisons / f"{index}.png")
        rows.append({"comparison_index": index, "image_name": f"cam/{index}.jpg", "lpips": lpips})
    score_csv = tmp_path / "scores.csv"
    with score_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    selected = export_extremes(score_csv=score_csv, patch_dir=patch, output_dir=tmp_path / "extremes")

    assert [row["comparison_index"] for row in selected[:3]] == ["1", "2", "0"]
    assert [row["comparison_index"] for row in selected[3:]] == ["4", "3", "5"]
    assert Image.open(selected[0]["gt_path"]).size == (4, 4)
    assert Image.open(selected[0]["render_path"]).size == (4, 4)


def test_export_extremes_documents_overlap_without_duplicate_rows(tmp_path: Path) -> None:
    patch = tmp_path / "patch"
    comparisons = patch / "eval_step_30000"
    comparisons.mkdir(parents=True)
    rows = []
    for index in range(3):
        Image.new("RGB", (12, 4)).save(comparisons / f"{index}.png")
        rows.append({"comparison_index": index, "image_name": f"{index}.jpg", "lpips": index})
    score_csv = tmp_path / "scores.csv"
    with score_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    selected = export_extremes(score_csv=score_csv, patch_dir=patch, output_dir=tmp_path / "extremes")

    assert len(selected) == 3
    assert all(row["class"] == "best_and_worst" for row in selected)
    assert all(row["overlap_reason"] for row in selected)
