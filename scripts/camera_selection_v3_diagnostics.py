"""Collect Camera Selection V3 diagnostics into scratch review folders."""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from reefs.io.yaml_json import read_json


def _patch_dirs(patches_dir: Path) -> list[Path]:
    return sorted(path for path in patches_dir.glob("p*") if path.is_dir())


def _copy_patch_pngs(
    *,
    patches_dir: Path,
    output_dir: Path,
    limit: int | None = None,
) -> list[dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for index, patch_dir in enumerate(_patch_dirs(patches_dir)):
        if limit is not None and index >= limit:
            break
        patch_id = patch_dir.name
        source_png = patch_dir / "patch_diagnostics" / "plot.png"
        metadata_path = patch_dir / "patch_metadata.json"
        destination_png = output_dir / f"{patch_id}_camera_selection.png"
        copied = False
        if source_png.exists():
            shutil.copy2(source_png, destination_png)
            copied = True
        metadata = read_json(metadata_path) if metadata_path.exists() else {}
        selector = metadata.get("selector", {}) if isinstance(metadata, dict) else {}
        coverage = selector.get("coverage", {}) if isinstance(selector, dict) else {}
        rows.append(
            {
                "patch_id": patch_id,
                "png": str(destination_png) if copied else "",
                "copied": copied,
                "selected_internal_count": coverage.get("selected_internal_count", ""),
                "rejected_internal_count": coverage.get("rejected_internal_count", ""),
                "selected_external_count": coverage.get("selected_external_count", ""),
                "unused_external_count": coverage.get("unused_external_count", ""),
                "warnings": "; ".join(str(item) for item in metadata.get("warnings", []))
                if isinstance(metadata, dict)
                else "",
            }
        )
    return rows


def _write_summary(rows: list[dict[str, object]], output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    summary_path = output_root / "summary.csv"
    fieldnames = [
        "dataset",
        "patch_id",
        "png",
        "copied",
        "selected_internal_count",
        "rejected_internal_count",
        "selected_external_count",
        "unused_external_count",
        "warnings",
    ]
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    notes = [
        "# Camera Selection V3 Review Notes",
        "",
        f"- PNG folders live under `{output_root}`.",
        f"- Summary CSV: `{summary_path}`.",
        "- Review kept internal, rejected internal, selected external, and unused external categories before LFS training.",
    ]
    (output_root / "review_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patches-dir", action="append", required=True, help="Path to a run's splat/patches directory.")
    parser.add_argument("--label", action="append", required=True, help="Output folder label for the matching --patches-dir.")
    parser.add_argument("--output-root", required=True, help="Scratch output root for collected PNGs.")
    parser.add_argument("--limit", type=int, default=None, help="Optional first-N patch limit for each input.")
    args = parser.parse_args()

    if len(args.patches_dir) != len(args.label):
        raise SystemExit("Provide the same number of --patches-dir and --label values.")

    output_root = Path(args.output_root)
    all_rows: list[dict[str, object]] = []
    for patches_dir_text, label in zip(args.patches_dir, args.label, strict=True):
        patches_dir = Path(patches_dir_text)
        output_dir = output_root / label
        rows = _copy_patch_pngs(patches_dir=patches_dir, output_dir=output_dir, limit=args.limit)
        for row in rows:
            all_rows.append({"dataset": label, **row})
    _write_summary(all_rows, output_root)


if __name__ == "__main__":
    main()
