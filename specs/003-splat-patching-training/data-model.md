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
- `image_count`: sparse registered image count.
- `point_count`: sparse point count.

Validation rules:
- Sparse files and undistorted images must exist before patching or training.
- Sparse image names must match available undistorted image relative paths.
- Feature 3 must use undistorted intrinsics, not raw sparse intrinsics.

## CameraPoseOutlierRecord

Represents one camera considered by the outlier filter.

Fields:
- `image_id`
- `image_name`
- `camera_center`
- `score`
- `threshold`
- `decision`: `kept`, `removed`, or `proposed`
- `reason`

Validation rules:
- Auto-removal is allowed only for a small configured maximum fraction.
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

## Patch

Represents one trainable patch dataset.

Fields:
- `patch_id`: stable identifier such as `p000`.
- `bounds`: relative scene-coordinate patch bounds.
- `buffer`: relative buffer value.
- `source_reconstruction`
- `selected_images`
- `selected_camera_count`
- `selected_sparse`
- `selected_images_dir`
- `diagnostics_dir`
- `status`: `valid`, `invalid`, `skipped`, or `failed`
- `invalid_reasons`
- `patch_affecting_config`

Validation rules:
- Patch IDs must be unique within a run.
- Selected images must exist under the undistorted image root.
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
- `coverage_plot`
- `coverage_histogram`
- `warnings`

Validation rules:
- Every generated patch should have a diagnostic record.
- Non-critical plot or table failures are logged but do not invalidate a valid
  patch sparse model.

## PatchReuseDecision

Represents an up-front decision for existing patch datasets.

Fields:
- `patch_id`
- `existing_patch_path`
- `decision`: `reuse`, `regenerate`, `skip`, or `stop`
- `reason`
- `patch_affecting_changes`
- `training_only_changes`

Validation rules:
- Valid existing patches are reused for training when only training settings
  changed.
- Patch-affecting changes require an up-front decision before patching or
  training starts.
- Non-interactive runs fail when a required decision is missing.

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
- `started_at`
- `ended_at`
- `duration_seconds`
- `return_code`
- `final_loss`
- `final_splat_count`
- `output_file`
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
- Completion below 80 percent is severe.
- Completion from 80 percent up to less than 100 percent is a warning.
- Invalid requested patches are skipped with severe warnings before any LFS job
  starts.
