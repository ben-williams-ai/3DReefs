# Quickstart: Splat Patching And Training

This quickstart verifies Feature 3 only. It assumes Feature 2 has produced
completed COLMAP undistorted outputs. It must not run cleanup, SOG compression,
final merging, NanoGS, LOD, PlayCanvas packaging, or mega-patching.

## 1. Prepare Environment

```bash
uv sync
uv run pytest tests/unit tests/integration
```

Confirm local tools/dependencies:

```bash
uv run python -c "import pycolmap, matplotlib"
uv run main.py --config configs/test.yml --steps foundation --resume-policy overwrite
```

Confirm `tools.lfs_bin` resolves through local config or `.env` and points to
LichtFeld Studio `v0.5.2`.

## 2. Prepare Source SfM Output

Use the completed test dataset SfM run from Feature 2:

```text
data/test_dataset/runs/<sfm_run_id>/
  sfm/
    undistorted/
      images/
      sparse/
```

The active config should point at the same `project.dir`.

## 3. Generate Patches Without Training

```bash
uv run main.py --config configs/test.yml --steps splat.patch --resume-policy overwrite
```

Expected:
- source undistorted SfM outputs are validated.
- outlier filtering runs first when enabled.
- patch folders are created under the active run's `splat/patches/`.
- no LFS training starts.

Inspect:

```text
<project.dir>/runs/<run_id>/splat/patches/p000/
  patch_metadata.json
  sparse/0/
  selected_images/
  patch_diagnostics/
```

## 4. Train One Patch With A Short Smoke Test

```bash
uv run main.py --config configs/test.yml --steps splat.train \
  --advanced.splat.train.patch_ids "[p000]" \
  --advanced.splat.train.num_iters 100
```

Expected:
- existing valid patch data is reused if patch-affecting settings have not
  changed.
- exactly one LFS process runs.
- patch training status is written even if the smoke run fails.

## 5. Train All Valid Patches Serially

```bash
uv run main.py --config configs/test.yml --steps splat.train --resume-policy resume
```

Expected:
- invalid requested patches are skipped with severe warnings before LFS starts.
- valid patches train one at a time.
- `logs/lfs.log`, patch-local logs, `timings.json`, and run manifest/status
  records identify every patch outcome.

## 6. Verify Failure Cases

Use temporary fixtures or copied run outputs to check:
- missing undistorted sparse fails before patching.
- missing selected image fails patch validation.
- unknown patch ID fails before LFS starts.
- outlier filtering blocks when proposed removals exceed the configured maximum
  fraction.
- non-interactive runs fail when existing-output decisions are required.
