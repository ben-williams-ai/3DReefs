#!/usr/bin/env python3
"""Summarise and aggregate Nebius Stage 1 ablation outputs."""

from __future__ import annotations

import argparse
import csv
import subprocess
from pathlib import Path


ENDPOINT = "https://storage.eu-north1.nebius.cloud"
BUCKET = "3dreefs-ben-eu-north1"
PREFIX = "experiments/ablations/stage1"
JOBS = [
    "sfm_dataset3_sfm_baseline",
    "sfm_dataset3_sfm_no_intrinsic_refine",
    "sfm_dataset3_sfm_seq_loop_only",
    "sfm_dataset3_sfm_features_4096",
    "sfm_dataset4_sfm_baseline",
    "sfm_dataset4_sfm_no_intrinsic_refine",
    "sfm_dataset4_sfm_seq_loop_only",
    "sfm_dataset4_sfm_features_4096",
]


def aws_s3(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["aws", "s3", *args, "--endpoint-url", ENDPOINT],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def cp_text(uri: str) -> str | None:
    result = aws_s3("cp", uri, "-", check=False)
    return result.stdout if result.returncode == 0 else None


def read_csv_uri(uri: str) -> list[dict[str, str]]:
    text = cp_text(uri)
    if not text:
        return []
    return list(csv.DictReader(text.splitlines()))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    fields = list(rows[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def status() -> int:
    print("| job | exit | sfm rows | splat rows | complete splats |")
    print("| --- | --- | ---: | ---: | ---: |")
    for job in JOBS:
        base = f"s3://{BUCKET}/{PREFIX}/runs/{job}"
        exit_text = (cp_text(f"{base}/{job}.exit") or "").strip()
        sfm_rows = read_csv_uri(f"{base}/ablation_eval/results_sfm.csv")
        splat_rows = read_csv_uri(f"{base}/ablation_eval/results_splat.csv")
        complete_splats = sum(1 for row in splat_rows if row.get("status", "").startswith("complete"))
        print(f"| `{job}` | {exit_text or 'pending'} | {len(sfm_rows)} | {len(splat_rows)} | {complete_splats} |")
    return 0


def aggregate(out_dir: Path) -> int:
    sfm_rows: list[dict[str, str]] = []
    splat_rows: list[dict[str, str]] = []
    for job in JOBS:
        base = f"s3://{BUCKET}/{PREFIX}/runs/{job}/ablation_eval"
        sfm_rows.extend(read_csv_uri(f"{base}/results_sfm.csv"))
        splat_rows.extend(read_csv_uri(f"{base}/results_splat.csv"))
    write_csv(out_dir / "results_sfm.csv", sfm_rows)
    write_csv(out_dir / "results_splat.csv", splat_rows)
    if sfm_rows:
        aws_s3("cp", str(out_dir / "results_sfm.csv"), f"s3://{BUCKET}/{PREFIX}/summary/results_sfm.csv")
    if splat_rows:
        aws_s3("cp", str(out_dir / "results_splat.csv"), f"s3://{BUCKET}/{PREFIX}/summary/results_splat.csv")
    print(f"sfm_rows={len(sfm_rows)} splat_rows={len(splat_rows)}")
    return 0 if len(sfm_rows) == 8 and len(splat_rows) == 80 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["status", "aggregate"])
    parser.add_argument("--out-dir", type=Path, default=Path("scratch/experiments/stage1_nebius_summary"))
    args = parser.parse_args()
    return status() if args.command == "status" else aggregate(args.out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
