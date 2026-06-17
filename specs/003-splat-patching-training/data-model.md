# Data Model: Splat Patching And Training

## SplatConfig Extensions

Feature 3 extends `advanced.splat` with outlier filtering, patching, and training
settings.

Top-level groups:
- `outlier_filter`
- `patching`
- `train`

Validation rules:
- Unknown keys continue to fail through the typed config loader.
- `patching.max_cameras` must be present and positive.
- `patching.max_cameras` is a user-selected GPU-fit limit; the system validates
  that generated patches do not exceed it but does not calculate a safe value
  from VRAM or image dimensions.
- `patching.buffer` defaults to `0.1` and is a relative scene-coordinate value.
- Multi-patch training concurrency is not a valid setting for this feature.

## SplatSourceReconstruction

Represents the validated Feature 2 output used by Feature 3.

Fields:
- `run_id`: source run identifier.
- `undistorted_images`: undistorted image root.
- `undistorted_sparse`: undistorted sparse model root.
- `cameras_file`: undistorted cameras file.
- `images_file`: undistorted images file.
- `points_file`: undistorted points file.
- `undistorted_intrinsics`: intrinsics from the undistorted sparse output.
- `image_count`: sparse registered image count.
- `point_count`: sparse point count.

Validation rules:
- Sparse files and undistorted images must exist before patching or training.
- Sparse image names must match available undistorted image relative paths.
- Sparse files must include cameras, images, and points in a COLMAP-readable
  model; text exports are written where required for auditability.
- Feature 3 must use undistorted intrinsics, not raw sparse intrinsics.

## CameraPoseOutlierRecord

Represents one camera considered by the outlier filter.

Fields:
- `image_id`
- `image_name`
- `camera_center`
- `method`: `iqr` or `percentile`
- `method_parameters`: detector settings such as `iqr_mult` or `percentile`
- `score`
- `threshold`
- `decision`: `kept`, `removed`, or `proposed`
- `reason`

Validation rules:
- Default detection uses IQR camera-centre bounds with `iqr_mult: 3.0`.
- Percentile detection remains available with default `percentile: 99.9`.
- Auto-removal is allowed only up to the configured maximum fraction, default
  `0.05`.
- If proposed removals exceed the maximum fraction, patching must stop with an
  ambiguous-reconstruction warning.

## FilteredReconstruction

Represents the reconstruction copy used by patching.

Fields:
- `source_sparse`
- `filtered_sparse`
- `filter_enabled`
- `dry_run`
- `removed_camera_count`
- `kept_camera_count`
- `removed_images`
- `diagnostics`

State transitions:
- `not_requested`
- `dry_run_reported`
- `complete_no_removals`
- `complete_removed_outliers`
- `blocked_ambiguous`
- `failed`

Validation rules:
- Source SfM output is never modified in place.
- Downstream patching uses `filtered_sparse` when filtering completes, otherwise
  the validated source sparse when no filtering is requested.
- Disabled filtering is a valid state: no outlier copy is written and downstream
  patching uses the validated source sparse.

## Patch

Represents one trainable patch dataset.

Fields:
- `patch_id`: stable identifier such as `p000`.
- `bounds`: required nested relative scene-coordinate patch bounds containing
  `min_x`, `max_x`, `min_y`, `max_y`, `min_z`, `max_z`, and `buffer`.
  Top-level boundary keys are not valid new metadata.
- `buffer`: relative buffer value.
- `source_reconstruction`
- `selected_images`
- `selected_camera_count`
- `selected_local_count`
- `selected_support_count`
- `selected_sparse`
- `selected_images_dir`
- `diagnostics_dir`
- `selector`: Feature 006 Target-Aware Spatial Greedy selector diagnostics,
  including selector name, version, signature, coverage summaries, warning
  thresholds, and warning flags.
- `status`: `valid`, `invalid`, `skipped`, or `failed`
- `invalid_reasons`
- `patch_affecting_config`

Validation rules:
- Patch IDs must be unique within a run.
- Selected images must exist under the undistorted image root.
- Camera selection uses the Feature 006 Target-Aware Spatial Greedy selector as
  the single supported behaviour. It combines sparse-track evidence and
  geometric target projection, protects local camera-position coverage, retains
  useful boundary/support views, and records warning-only poor-coverage
  conditions without automatically blocking training.
- `valid`: selected images exist, selected camera count is within
  `patching.max_cameras`, sparse export succeeded, and enough sparse support is
  present for LFS staging.
- `invalid`: patch generation completed but selected images, sparse support,
  selected camera count, or metadata validation failed.
- `skipped`: patch was not requested for the current training command, or was an
  invalid requested patch skipped before LFS starts.
- `failed`: patch generation or export failed in a way that blocks using the
  patch dataset.
- Sparse export failures fail patch generation.
- Diagnostic export failures may warn and continue when the patch dataset is
  otherwise valid.

## PatchSelectionDiagnostic

Represents inspectable camera-selection evidence for one patch.

Fields:
- `patch_id`
- `camera_coverage_rows`
- `selected_count`
- `unselected_count`
- `local_count`
- `support_count`
- `selection_scores`: per-camera track evidence, projection evidence, hybrid
  body/boundary scores, target image share, local-cell/view-bin marginal gains,
  support/spillover penalties, selection reason, and warning flags.
- `coverage_plot`
- `histogram`
- `warnings`

Validation rules:
- Every generated patch should have a diagnostic record. The camera coverage
  table and generation log are required for auditability when patch generation
  succeeds.
- Non-critical plot or table failures are logged but do not invalidate a valid
  patch sparse model.

## PatchReuseDecision

Represents an up-front decision for existing patch datasets.

Fields:
- `patch_id`
- `existing_patch_path`
- `decision`: `reuse`, `regenerate`, `retrain`, `skip`, or `stop`
- `reason`
- `patch_affecting_changes`
- `training_only_changes`

Validation rules:
- Valid existing patches are reused for training when only training settings
  changed.
- Patch-affecting changes require an up-front decision before patching or
  training starts.
- Non-interactive runs fail when a required decision is missing.
- `reuse` means keep valid existing patch data for the requested stage.
- `regenerate` means overwrite/recreate patch data because patch-affecting
  inputs changed or the user chose overwrite.
- `retrain` applies only to training outputs and means run LFS again for missing,
  failed, or incomplete patch training.
- `skip` means do not run work for that patch in this request and record the
  reason.
- `stop` means abort before requested work starts.

## PatchTrainingRun

Represents one LFS training attempt for one patch.

Fields:
- `patch_id`
- `requested_iterations`
- `completed_iterations`
- `completion_ratio`
- `num_splats_per_patch`
- `strategy`
- `headless`
- `max_width`
- `started_at`
- `ended_at`
- `duration_seconds`
- `return_code`
- `final_loss`
- `final_splat_count`
- `output_file`
- `original_output_file`
- `loss_history_file`
- `log_file`
- `status`: `complete`, `warning`, `severe_warning`, `failed`, `skipped`, or
  `not_requested`
- `reason`

State transitions:
- `queued`
- `running`
- `complete`
- `warning`
- `severe_warning`
- `failed`
- `skipped`

Validation rules:
- Exactly one patch training run may be active within one pipeline process.
- `complete`: completed requested iterations and expected output exists.
- `warning`: completed at least 80 percent but less than 100 percent and a
  usable output exists.
- `severe_warning`: completed less than 80 percent but a usable partial output
  exists.
- `failed`: LFS could not start, returned a blocking failure, or no usable output
  exists.
- `skipped`: requested patch was invalid before training or excluded by an
  up-front decision.
- `not_requested`: patch existed but was not included in the requested patch
  list.
- Invalid requested patches are skipped with severe warnings before any LFS job
  starts.
- If LFS progress parsing fails, status classification must still use process
  return code and output artefact presence, and record a separate parser warning
- Completed runs expose `splat_finished.ply` as the stable `output_file` while
  preserving the original LFS iteration-stamped output in `original_output_file`.
- Usable incomplete runs keep the iteration-stamped output as `output_file`.
- `loss_history_file` points to the per-patch CSV loss/progress record when
  progress parsing produced rows.
  rather than treating parsing failure alone as training failure.
