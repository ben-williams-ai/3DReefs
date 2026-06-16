# Data Model: Hybrid Camera Selection

## PatchTargetRegion

Represents the stored patch bounds used as the selector target.

Fields:
- `patch_id`
- `bounds`: nested `min_x`, `max_x`, `min_y`, `max_y`, `min_z`, `max_z`,
  `buffer`
- `target_samples`: bounded sample points inside `bounds`
- `body_sample_count`
- `boundary_sample_count`
- `cell_grid`: coarse spatial cells used for coverage diagnostics

Validation rules:
- Bounds must be valid nested Feature 3 bounds.
- The selector must not expand `bounds` again.
- Boundary samples are samples inside the existing boundary band; body samples
  are the remaining target samples.

## CandidateCamera

Represents one image considered for a patch.

Fields:
- `image_id`
- `image_name`
- `camera_id`
- `camera_center`
- `pool`: `local`, `support`, or `target_observer`
- `source_patch`
- `local_position_cell`
- `view_azimuth_bin`
- `view_elevation_bin`
- `target_image_share`
- `target_share_warning`

Validation rules:
- Candidates may come from local camera centres, one-ring neighbours, track
  observers of target points, or geometric projection into the target region.
- `pool` is diagnostic metadata and a soft selection prior, not a hard quota.
- Candidate image names must exist in the source sparse model and selected image
  root.

## HybridVisibilityEvidence

Represents per-camera target observation evidence before greedy selection.

Fields:
- `track_body_score`
- `track_boundary_score`
- `projection_body_score`
- `projection_boundary_score`
- `hybrid_body_score`
- `hybrid_boundary_score`
- `weighted_track_point_count`
- `visible_target_sample_ids`
- `visible_body_sample_ids`
- `visible_boundary_sample_ids`
- `median_visible_depth`
- `density_weight_summary`

Validation rules:
- Sparse point contributions are density-weighted within the patch target.
- Track and projection scores are normalised within the patch.
- Visibility scores use either-signal fusion so either strong tracks or strong projection
  can identify a useful camera.

## GreedySelectionState

Represents incremental state while selecting cameras for one patch.

Fields:
- `selected_image_ids`
- `covered_body_samples`
- `covered_boundary_samples`
- `covered_local_position_cells`
- `covered_view_bins`
- `selected_local_count`
- `selected_support_count`
- `selected_nonlocal_fraction`
- `current_warning_flags`

Validation rules:
- Selection stops at `patching.max_cameras`.
- A camera is selected only when it adds useful marginal value or is needed to
  preserve local acquisition coverage under weak sparse evidence.
- Duplicate image IDs are not allowed.

## SelectionDiagnosticRecord

Represents one row in the per-patch camera diagnostic table.

Fields:
- `patch_id`
- `image_id`
- `image_name`
- `selection_role`: `selected` or `unselected`
- `pool`
- `source_patch`
- `selection_reason`
- `rejection_reason`
- `hybrid_body_score`
- `hybrid_boundary_score`
- `track_body_score`
- `track_boundary_score`
- `projection_body_score`
- `projection_boundary_score`
- `target_image_share`
- `new_body_sample_gain`
- `new_boundary_sample_gain`
- `new_local_cell_gain`
- `view_bin_gain`
- `nonlocal_penalty`
- `spillover_penalty`
- `camera_x`
- `camera_y`
- `camera_z`

Validation rules:
- Every candidate considered by the selector should have a diagnostic row.
- Rows must allow a researcher to distinguish selected local, rejected local,
  selected support/nonlocal, and unused support/nonlocal cameras.

## PatchMetadataSelectorBlock

Extends Feature 3 `patch_metadata.json`.

Fields:
- `selector.name`: `target_aware_spatial_greedy`
- `selector.version`
- `selector.signature`
- `selector.settings`
- `selector.coverage.body`
- `selector.coverage.boundary`
- `selector.coverage.local_position_cells`
- `selector.coverage.view_bins`
- `selector.selected_local_count`
- `selector.selected_support_count`
- `selector.warning_thresholds`
- `selector.warning_flags`

Validation rules:
- The selector signature includes all selector-affecting settings and relevant
  input fingerprints.
- Existing patch outputs with incompatible selector signatures require an
  up-front reuse or overwrite decision.
- Named warning thresholds are recorded so poor-coverage, small-target-share, and
  excessive-support warnings are explainable after the run.
- Poor coverage warning flags do not make an otherwise valid patch invalid.

## State Transitions

Patch selection states:
- `not_requested`
- `pending`
- `running`
- `complete_valid`
- `complete_with_warnings`
- `failed_invalid_inputs`
- `failed_invalid_outputs`
- `reused`
- `overwritten`

Rules:
- Invalid inputs fail before training starts.
- Non-critical diagnostic export failures can produce `complete_with_warnings`.
- Poor selector coverage produces `complete_with_warnings` but remains trainable.
