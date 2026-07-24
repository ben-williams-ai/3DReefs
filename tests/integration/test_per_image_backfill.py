"""Integration checks for the per-image backfill command."""

from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image

from reefs.eval.per_image_backfill import SCORE_FIELDS, combine_score_csvs, export_extremes


def test_combined_csv_and_six_extreme_exports(tmp_path: Path) -> None:
    patch = tmp_path / "raw" / "dataset1" / "p000"
    comparisons = patch / "eval_step_30000"
    comparisons.mkdir(parents=True)
    rows = []
    for index in range(6):
        comparison = Image.new("RGB", (12, 4))
        comparison.paste(Image.new("RGB", (4, 4), (index, 0, 0)), (0, 0))
        comparison.paste(Image.new("RGB", (4, 4), (0, index, 0)), (8, 0))
        comparison.save(comparisons / f"{index}.png")
        rows.append(
            {
                **{field: "" for field in SCORE_FIELDS},
                "dataset": "dataset1",
                "patch_id": "p000",
                "comparison_index": str(index),
                "image_name": f"cam/{index}.jpg",
                "lpips": str(index / 10),
            }
        )
    patch_csv = tmp_path / "p000.csv"
    with patch_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    combined = combine_score_csvs(inputs=[patch_csv], output_csv=tmp_path / "combined.csv")
    selected = export_extremes(
        score_csv=patch_csv,
        patch_dir=patch,
        output_dir=tmp_path / "extremes",
    )

    assert len(combined) == 6
    assert len(selected) == 6
    assert len(list((tmp_path / "extremes").rglob("*.png"))) == 18
