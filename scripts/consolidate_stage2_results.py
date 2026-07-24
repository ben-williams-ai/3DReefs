#!/usr/bin/env python3
"""Build and validate the canonical Stage 2 results archive."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "experiments/results/stage2"
KEY_FIELDS = (
    "dataset_id",
    "training_resolution",
    "patch_size",
    "gaussian_limit",
    "patch_id",
)
RAW_FIELDS = {
    "dataset": "dataset",
    "training_resolution": "training_resolution",
    "patch_size": "patch_size",
    "gaussian_limit": "splat_count",
    "ssim": "ssim",
    "psnr": "psnr",
    "lpips": "lpips",
    "actual_splat_count": "actual_splat_count",
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read one CSV while preserving its declared column order."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    """Write rows atomically with stable Unix newlines."""
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def download_sources(
    rows: list[dict[str, str]], runs_dir: Path
) -> list[dict[str, object]]:
    """Mirror each authoritative per-run ledger and return its checksum record."""
    inventory = []
    sources = {
        (row["outer_run_id"], row["source_uri"])
        for row in rows
        if row["source_uri"]
    }
    for outer_run_id, source_uri in sorted(sources):
        target = runs_dir / outer_run_id / "results_splat.csv"
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["aws", "s3", "cp", source_uri, str(target), "--only-show-errors"],
            check=True,
        )
        inventory.append(
            {
                "outer_run_id": outer_run_id,
                "source_uri": source_uri,
                "local_path": str(target.relative_to(ROOT)),
                "bytes": target.stat().st_size,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    return inventory


def validate(
    rows: list[dict[str, str]],
    inventory: list[dict[str, object]],
) -> dict[str, object]:
    """Validate uniqueness, successful metrics and exact remote provenance."""
    keys = [tuple(row[field] for field in KEY_FIELDS) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate canonical Stage 2 scientific rows")

    raw_by_source: dict[str, dict[str, dict[str, str]]] = {}
    for source in inventory:
        _, raw_rows = read_csv(ROOT / str(source["local_path"]))
        raw_by_source[str(source["source_uri"])] = {
            row["job_id"]: row for row in raw_rows
        }

    for row in rows:
        raw_id = f"splat_eval_{row['run_id']}_{row['patch_id']}"
        raw = raw_by_source.get(row["source_uri"], {}).get(raw_id)
        if raw is None:
            raise ValueError(f"missing authoritative source row: {raw_id}")
        for canonical_field, raw_field in RAW_FIELDS.items():
            if row[canonical_field] != raw[raw_field]:
                raise ValueError(
                    f"{raw_id}: {canonical_field} differs from authoritative source"
                )
        if row["status"] != raw["status"].upper():
            raise ValueError(f"{raw_id}: status differs from authoritative source")
        if row["status"] == "COMPLETE":
            if not all(row[field] for field in ("ssim", "psnr", "lpips")):
                raise ValueError(f"{raw_id}: successful row has blank metrics")
            if row["actual_splat_count"] != row["gaussian_limit"]:
                raise ValueError(f"{raw_id}: successful row has collapsed splat count")

    successes = [row for row in rows if row["status"] == "COMPLETE"]
    failures = [row for row in rows if row["status"] != "COMPLETE"]
    cells = {
        (
            row["dataset_id"],
            row["training_resolution"],
            row["patch_size"],
            row["gaussian_limit"],
        )
        for row in successes
    }
    return {
        "all_rows": len(rows),
        "successful_rows": len(successes),
        "failure_rows": len(failures),
        "successful_cells": len(cells),
        "source_ledgers": len(inventory),
        "rows_by_dataset": dict(sorted(Counter(row["dataset"] for row in rows).items())),
        "successful_rows_by_dataset": dict(
            sorted(Counter(row["dataset"] for row in successes).items())
        ),
    }


def consolidate(source: Path, results_dir: Path) -> dict[str, object]:
    """Split the audit ledger, mirror sources and write validation records."""
    fields, rows = read_csv(source)
    if not rows:
        raise ValueError(f"empty Stage 2 source ledger: {source}")

    runs_dir = results_dir / "runs"
    inventory = download_sources(rows, runs_dir)
    report = validate(rows, inventory)
    successes = [row for row in rows if row["status"] == "COMPLETE"]
    failures = [row for row in rows if row["status"] != "COMPLETE"]

    write_csv(results_dir / "stage2_all_results.csv", fields, rows)
    write_csv(results_dir / "stage2_results.csv", fields, successes)
    write_csv(results_dir / "stage2_failures.csv", fields, failures)

    inventory_path = results_dir / "source_inventory.csv"
    inventory_fields = [
        "outer_run_id",
        "source_uri",
        "local_path",
        "bytes",
        "sha256",
    ]
    write_csv(
        inventory_path,
        inventory_fields,
        [{field: str(row[field]) for field in inventory_fields} for row in inventory],
    )
    (results_dir / "validation_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    """Run consolidation from an explicit source or the current master."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=RESULTS_DIR / "stage2_all_results.csv",
    )
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()
    report = consolidate(args.source.resolve(), args.results_dir.resolve())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
