"""Score saved LFS comparisons or export deterministic LPIPS extremes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reefs.eval.per_image_backfill import combine_score_csvs, export_extremes, score_patch


def main() -> None:
    """Run one resumable patch operation."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    score = subparsers.add_parser("score-patch")
    score.add_argument("--patch-dir", type=Path, required=True)
    score.add_argument("--output-csv", type=Path, required=True)
    score.add_argument("--provenance", type=Path, required=True)
    export = subparsers.add_parser("export-patch")
    export.add_argument("--patch-dir", type=Path, required=True)
    export.add_argument("--score-csv", type=Path, required=True)
    export.add_argument("--output-dir", type=Path, required=True)
    combine = subparsers.add_parser("combine")
    combine.add_argument("--input", type=Path, action="append", required=True)
    combine.add_argument("--output-csv", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "score-patch":
        provenance = json.loads(args.provenance.read_text(encoding="utf-8"))
        rows = score_patch(patch_dir=args.patch_dir, output_csv=args.output_csv, provenance=provenance)
    elif args.command == "export-patch":
        rows = export_extremes(score_csv=args.score_csv, patch_dir=args.patch_dir, output_dir=args.output_dir)
    else:
        rows = combine_score_csvs(inputs=args.input, output_csv=args.output_csv)
    print(json.dumps({"status": "complete", "rows": len(rows)}))


if __name__ == "__main__":
    main()
