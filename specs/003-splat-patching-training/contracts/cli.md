# CLI Contract: Splat Patching And Training

## Run Full Splat Patching And Training

```bash
uv run main.py --config <config.yml> --steps splat
```

Behaviour:
- Runs foundation preflight.
- Validates Feature 2 undistorted SfM outputs.
- Runs camera pose outlier filtering when enabled; when disabled, records that
  filtering was not requested and patches from the validated source sparse.
- Generates or reuses valid patches.
- Trains requested valid patches exactly one at a time.
- Does not run patch cleanup, cleaned patch merging, final SOG conversion,
  NanoGS, LOD, PlayCanvas, or mega-patching.

## Run Selected Splat Substages

```bash
uv run main.py --config <config.yml> --steps splat.patch
uv run main.py --config <config.yml> --steps splat.train
uv run main.py --config <config.yml> --steps splat.outlier_filter,splat.patch
```

Supported step names for this feature:
- `splat`
- `splat.preflight`
- `splat.outlier_filter`
- `splat.patch`
- `splat.train`

All requested steps are inspected for prior outputs before any step starts.
Conditions that would otherwise prompt in interactive mode fail before work
starts when the run is non-interactive and no explicit resume policy/decision was
provided.

## Train Selected Patches

```bash
uv run main.py --config <config.yml> --steps splat.train --advanced.splat.train.patch_ids "[p000,p005]"
```

Behaviour:
- Only requested patch IDs are considered for training.
- Unknown patch IDs fail before LFS starts.
- Invalid requested patches are skipped with severe warnings recorded before the
  first LFS job starts.
- Valid requested patches train serially.

## Dry-Run Outlier Filtering

```bash
uv run main.py --config <config.yml> --steps splat.outlier_filter --advanced.splat.outlier_filter.dry_run true
```

Behaviour:
- Reports proposed removals and diagnostics.
- Does not change the reconstruction used by patching.
- Does not start patching or training unless those stages are also requested and
  valid source outputs exist.

## Resume And Reuse

Existing `--resume-policy` applies to patching and training:
- `prompt`: ask interactively, fail in non-interactive contexts when a decision is
  required.
- `resume`: reuse valid outputs where allowed.
- `overwrite`: regenerate/retrain requested outputs.
- `fail`: fail if any requested stage has prior outputs requiring a decision.

Patch reuse rules:
- Valid existing patches are reused for training when only training settings have
  changed.
- SfM source, outlier filtering, patch geometry/buffer, maximum cameras, camera
  selection, or image source/layout changes are patch-affecting and require an
  up-front decision.
- `resume` reuses valid existing stage outputs.
- `overwrite` regenerates patch outputs or retrains requested training outputs.
- `skip` records that a patch/stage is intentionally not processed in this
  request.
- `fail` stops before requested work starts when prior outputs require a
  decision.

## Exit Behaviour

- `0`: requested splat patching/training stages completed, were validly reused,
  or valid patches trained while invalid requested patches were explicitly
  skipped.
- Non-zero: validation failed, required source output missing, required decision
  missing, outlier filtering blocked as ambiguous, patch export failed, all
  requested patches were invalid, LFS failed in a blocking way, or required run
  records could not be written.
