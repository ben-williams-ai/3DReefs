# Data Model: Camera Selection V2

## PatchFootprint

Represents the stored patch bounds already produced by patch generation.

Fields:

- `patch_id`
- `min_x`, `max_x`, `min_y`, `max_y`
- `min_z`, `max_z`
- `buffer`

Rules:

- Bounds are read-only input to camera selection.
- The stored buffer is ordinary footprint area.
- The selector does not expand bounds again.

## FootprintTarget

Represents sampled target evidence for a patch footprint.

Fields:

- `patch_id`
- `scene_registered_image_count`
- `scene_target_cell_count`
- `patch_target_cell_count`
- `grid_x_count`
- `grid_y_count`
- `samples`

Rules:

- `scene_target_cell_count = round(scene_registered_image_count / 5)`.
- `patch_target_cell_count` is allocated by patch area, with a tiny minimum of
  four cells.
- Grid dimensions follow patch aspect ratio.
- Samples cover the full stored patch footprint, independent of sparse-point
  density.

## TargetSample

Represents one 3D point used to test whether cameras see the patch footprint.

Fields:

- `sample_id`
- `cell_id`
- `x`, `y`, `z`
- `height_source`: `local_points`, `neighbour_points`, or `patch_fallback`

Rules:

- Local sparse-point heights are robustly filtered before use.
- Empty cells use neighbouring-cell heights where available.
- If no neighbouring evidence exists, use a robust patch-level height.
- Flat cells may have one sample height; vertically varied cells may have more.

## CandidateCamera

Represents one camera considered for a patch.

Fields:

- `image_id`
- `image_name`
- `camera_center`
- `camera_role`: `internal` or `external`
- `candidate_source`: `internal`, `one_ring_neighbour`, `matched_track`, or
  `geometric_target`
- `matched_track_evidence`
- `geometric_visibility_evidence`
- `target_image_share`
- `view_direction_bin`

Rules:

- Internal cameras have centres inside the patch footprint.
- External cameras have centres outside the patch footprint.
- External candidates are allowed from one-ring neighbour context or direct
  matched/geometric target evidence.
- Either matched-track evidence or geometric visibility can make a camera useful.
- Tiny target image share can demote or reject sliver views.

## SelectedCameraSet

Represents final cameras assigned to a patch.

Fields:

- `patch_id`
- `selected_image_ids`
- `selected_internal_count`
- `selected_external_count`
- `rejected_internal_count`
- `unused_external_count`
- `selector_name`
- `selector_version`
- `selector_signature`
- `warnings`

Rules:

- Selected count never exceeds `patching.max_cameras`.
- Selection continues while useful candidates remain and capacity remains.
- Incompatible selector signatures require up-front reuse or overwrite decision.

## SelectionDiagnostic

Represents human-readable evidence for selection decisions.

Fields:

- `camera_coverage.csv`
- `plot.png`
- `plot.html`
- `histogram.png`
- `generation.log`

Rules:

- Diagnostics distinguish selected internal, rejected internal, selected
  external, and unused external cameras.
- Diagnostic export failure is warning-only if selected patch outputs are valid.
