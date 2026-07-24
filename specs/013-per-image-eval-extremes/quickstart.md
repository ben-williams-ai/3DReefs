# Quickstart: Per-Image Evaluation Extremes

All commands run from the repository root. Exact CLI arguments will be finalised by implementation; no command may bypass accepted-run validation.

```bash
uv run python scripts/backfill_per_image_eval.py inventory --output data/patch-results/inventory
uv run python scripts/backfill_per_image_eval.py score --root data/patch-results
uv run python scripts/backfill_per_image_eval.py export --root data/patch-results
uv run python scripts/backfill_per_image_eval.py validate --root data/patch-results
```

Expected terminal outputs:

- accepted inventory for six datasets and sixty patches;
- checksum-verified immutable raw inputs;
- six per-dataset score CSVs and one combined CSV;
- one best/worst selection CSV per patch;
- validation and visual-inspection reports.

Run focused checks before real data:

```bash
uv run pytest -q tests/unit/test_eval_image_metrics.py tests/unit/test_eval_lpips.py tests/unit/test_per_image_backfill.py tests/integration/test_per_image_backfill.py
python -m compileall -q src/reefs/eval scripts/backfill_per_image_eval.py
git diff --check
```
