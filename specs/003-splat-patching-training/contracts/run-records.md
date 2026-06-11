# Run Record Contract: Splat Patching And Training

Feature 3 extends the Feature 1 run record under:

```text
<project.dir>/runs/<run_id>/
```

## Required Additional Files/Directories

```text
logs/
  lfs.log
splat/
  outlier_filter/
  patches/
diagnostics/
  # optional summary plots/tables that are not patch-local
```

`logs/warnings.log` is created only when warnings occur.

## Manifest Additions

`run_manifest.json` must include a `splat` object after patching or training
stages run or are reused.

Required fields:
- `source_sfm_run_id`
- `source_undistorted_sparse`
- `source_undistorted_images`
- `outlier_filter`
- `patching`
- `training`
- `patch_reuse_decisions`
- `warnings`

## Outlier Filter Manifest Fields

- `enabled`
- `dry_run`
- `method`
- `method_parameters`
- `source_sparse`
- `filtered_sparse`
- `removed_camera_count`
- `kept_camera_count`
- `max_removal_fraction`
- `status`
- `diagnostics`

## Patching Manifest Fields

- `patches_root`
- `patch_count`
- `valid_patch_count`
- `invalid_patch_count`
- `max_cameras`
- `buffer`
- `patch_affecting_config`
- `patches`: list of patch metadata summaries

## Training Manifest Fields

- `requested_patch_ids`
- `trained_patch_ids`
- `skipped_patch_ids`
- `not_requested_patch_ids`
- `num_iters`
- `num_splats_per_patch`
- `strategy`
- `serial_training`: `true`
- `patch_statuses`: list of patch training status summaries

## Status Additions

`run_status.json` stage names may include:
- `splat.preflight`
- `splat.outlier_filter`
- `splat.patch`
- `splat.train`
- `splat.train.<patch_id>`

## Timings Additions

`timings.json` must record exact start/end/duration/status for:
- splat preflight.
- outlier filtering.
- patch generation.
- patch diagnostics where separately timed.
- each requested patch training job.

Patch-level timing must be queryable without parsing `logs/lfs.log`.

## Warning Events

Warnings may include:
- no outliers removed.
- proposed outliers exceeded maximum removal fraction.
- reused existing patch datasets.
- patch-affecting settings changed.
- diagnostic plot/table generation failed.
- invalid patch skipped.
- LFS progress parsing failed.
- training completed below 100 percent.
- training completed below 80 percent.

Warnings must be visible in `logs/pipeline.log`; `logs/warnings.log` is created
only when warnings occur.

## Existing-Output Decision Records

Existing-output decisions must be recorded before requested splat stages start.
Each decision record includes:
- `stage`: requested stage affected by the decision.
- `patch_id`: patch identifier when the decision is patch-specific, otherwise
  `null`.
- `decision`: `reuse`, `regenerate`, `retrain`, `skip`, or `stop`.
- `reason`: human-readable explanation.
- `config_changes`: patch-affecting or training-only changes considered.
- `decided_at`: timestamp before the first requested splat stage begins.
