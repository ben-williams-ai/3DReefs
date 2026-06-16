# Patch Selection Artefact Contract

Feature 006 updates the Feature 3 patch artefacts without changing the directory
layout.

## Patch Metadata

Every generated patch metadata file must include the Feature 3 fields plus a
selector block:

```json
{
  "patch_id": "p000",
  "bounds": {
    "min_x": 0.0,
    "max_x": 1.0,
    "min_y": 0.0,
    "max_y": 1.0,
    "min_z": 0.0,
    "max_z": 1.0,
    "buffer": 0.1
  },
  "selected_images": [],
  "selected_camera_count": 0,
  "selected_local_count": 0,
  "selected_support_count": 0,
  "selector": {
    "name": "target_aware_spatial_greedy",
    "version": "1",
    "signature": "<stable selector-affecting signature>",
    "target_sample_count": 0,
    "body_sample_count": 0,
    "boundary_sample_count": 0,
    "coverage": {
      "body": 0.0,
      "boundary": 0.0,
      "local_position_cells": 0.0,
      "view_bins": 0.0
    },
    "target_image_share": {
      "median_selected": 0.0,
      "min_selected": 0.0
    },
    "warning_thresholds": {
      "meaningful_target_coverage": 0.0,
      "small_target_share": 0.0,
      "excessive_support_fraction": 0.0
    },
    "warnings": []
  }
}
```

Validation rules:
- `selector.name` must be `target_aware_spatial_greedy`.
- No legacy selector-mode field is valid for this feature.
- `bounds` remains the stored target region and must not be expanded by this
  selector.
- `selected_camera_count` must be less than or equal to `patching.max_cameras`.
- Warning-only poor coverage does not invalidate the patch.
- Warning thresholds must be named in metadata so diagnostics can explain why a
  patch received a warning.

## Camera Coverage CSV

`patch_diagnostics/camera_coverage.csv` must include one row per candidate camera
and the following columns:

```text
patch_id
image_id
image_name
selection_role
pool
source_patch
selection_reason
rejection_reason
hybrid_body_score
hybrid_boundary_score
track_body_score
track_boundary_score
projection_body_score
projection_boundary_score
target_image_share
new_body_sample_gain
new_boundary_sample_gain
new_local_cell_gain
view_bin_gain
nonlocal_penalty
spillover_penalty
warning_flags
camera_x
camera_y
camera_z
```

Required behaviour:
- Selected local cameras, rejected local cameras, selected support/nonlocal
  cameras, and unused support/nonlocal cameras must be distinguishable from the
  CSV alone.
- Missing or malformed required CSV rows are blocking when patch generation
  otherwise claims success.

## Sparse Patch Export

The selected sparse model remains the Feature 3 patch sparse output:

```text
splat/patches/<patch_id>/sparse/0/
  cameras.txt
  images.txt
  points3D.txt
```

Required behaviour:
- Only selected images are included.
- Point tracks preserve valid COLMAP point2D indices for selected images.
- Source SfM sparse outputs are not modified.
