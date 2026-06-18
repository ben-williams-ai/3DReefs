# Quickstart: Camera Selection V3

## 1. Run Unit Checks

```bash
uv run pytest -q tests/unit/test_splat_config.py tests/unit/test_patch_bounds.py tests/unit/test_patch_selection.py tests/unit/test_patch_diagnostics.py tests/unit/test_patch_validation.py
```

## 2. Run Full Test Suite

```bash
uv run pytest -q
```

## 3. Generate Diagnostics Only

Use existing local dataset configs and run only patch generation/diagnostic steps. Do not run LFS training until the PNGs look sane.

Sweep:

```text
external_support_fraction = 0.05
external_support_fraction = 0.10
external_support_fraction = 0.15
```

Expected output root:

```text
scratch/camera_selection_v3_pngs_<timestamp>/
```

After patch diagnostics exist under run directories, collect review PNGs with:

```bash
uv run python scripts/camera_selection_v3_diagnostics.py \
  --patches-dir <DATASET1_RUN>/splat/patches --label dataset1_400_support010 \
  --patches-dir <DATASET2_RUN>/splat/patches --label dataset2_400_support010 \
  --output-root scratch/camera_selection_v3_pngs_<timestamp>
```

Expected folders:

```text
dataset1_400_support005/
dataset1_400_support010/
dataset1_400_support015/
dataset2_400_support005/
dataset2_400_support010/
dataset2_400_support015/
```

Each folder contains only:

```text
p000_camera_selection.png
p001_camera_selection.png
...
```

Also write:

```text
summary.csv
review_notes.md
```

## 4. Review Known Bad Cases

Check Dataset 1 p002 and p007 side-by-side outputs:

```text
scratch/camera_selection_v3_comparison/dataset1_400_p002/
scratch/camera_selection_v3_comparison/dataset1_400_p007/
```

Each case should include V2 bad evidence and V3 support fractions `0.05`, `0.10`, and `0.15`.

Pass criteria:

- p002 keeps useful internal strip cameras.
- p007 keeps useful internal bend cameras.
- External support stays within allowance.
- No selected external camera comes from a non-neighbouring patch.
- `external_support_fraction: 0` produces internal-only selections.
- Polish Town first 20 patches at 200 cameras include useful neighbouring oblique support when support is enabled.

## 5. Proceed To Training

Only run LFS patch training after diagnostics are reviewed and accepted.
