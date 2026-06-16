# Quickstart: Hybrid Camera Selection

## Preconditions

- A completed Feature 2 SfM run exists.
- Feature 3 patching dependencies are configured.
- The run can be regenerated without modifying source SfM outputs.

## Run Patch Selection On The Test Dataset

Use an existing run id from the test dataset:

```bash
uv run main.py \
  --config configs/test.yml \
  --run-id <test-run-id> \
  --steps splat.patch \
  --resume-policy overwrite
```

Inspect:

```text
data/test_dataset/runs/<test-run-id>/splat/patches/patch_summary.png
data/test_dataset/runs/<test-run-id>/splat/patches/p000/patch_metadata.json
data/test_dataset/runs/<test-run-id>/splat/patches/p000/patch_diagnostics/
```

## Validate Known Reef Patches Before Retraining

Regenerate patch selection only for an existing completed SfM/splat run:

```bash
uv run main.py \
  --config configs/datasets/dataset_01.yml \
  --run-id <dataset-1-run-id> \
  --steps splat.patch \
  --resume-policy overwrite
```

Check known problematic patches before launching any LFS training:

```text
data/dataset1/runs/<dataset-1-run-id>/splat/patches/p000/patch_diagnostics/
data/dataset1/runs/<dataset-1-run-id>/splat/patches/p006/patch_diagnostics/
```

Expected inspection result:
- selected local cameras no longer leave a large hollow acquisition strip
- useful support cameras remain visible where they improve boundaries
- warnings are readable from metadata and diagnostics

## Run Automated Checks

```bash
uv run pytest \
  tests/unit/test_patch_visibility.py \
  tests/unit/test_patch_selection.py \
  tests/unit/test_patch_selection_diagnostics.py \
  tests/unit/test_patch_selection_reuse.py \
  tests/integration/test_splat_hybrid_camera_selection.py \
  -q
```

## Out Of Scope For This Feature

Do not use this feature to launch expensive LFS retraining, cleanup, merge, or
SOG compression. Those stages should consume the selected patch outputs only
after diagnostics look sensible.
