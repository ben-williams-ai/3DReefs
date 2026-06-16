# Patch Artefact Contract

Feature 3 writes patch artefacts under the active run directory:

```text
<project.dir>/runs/<run_id>/
  splat/
    outlier_filter/
    patches/
      p000/
      p001/
```

## Outlier Filter Artefacts

```text
splat/outlier_filter/
  filter_summary.json
  filtered_sparse/0/
    cameras.bin
    images.bin
    points3D.bin
    cameras.txt
    images.txt
    points3D.txt
  diagnostics/
    camera_pose_top_before.png
    camera_pose_top_after.png
    camera_pose_side_before.png
    camera_pose_side_after.png
```

Required behaviour:
- `filter_summary.json` is written even when no cameras are removed.
- `filtered_sparse/0/` is written when filtering is enabled and not dry-run.
- If proposed removals exceed the configured maximum removal fraction,
  `filter_summary.json` records the ambiguous condition and patching stops.

## Patch Directory

Every generated patch has:

```text
splat/patches/p000/
  patch_metadata.json
  sparse/0/
    cameras.bin
    images.bin
    points3D.bin
    cameras.txt
    images.txt
    points3D.txt
  selected_images/
  patch_diagnostics/
    camera_coverage.csv
    plot.png
    plot.html
    histogram.png
    generation.log
  splat/
```

Required behaviour:
- `patch_metadata.json` is mandatory.
- Patch bounds must be stored only inside the nested `bounds` object. Top-level
  `min_x`, `max_x`, `min_y`, `max_y`, `min_z`, or `max_z` keys are historical
  old-pipeline evidence and are not valid new metadata.
- `sparse/0/` is mandatory for valid patches.
- `selected_images/` must expose only images selected for that patch, preferably
  via symlinks to undistorted images.
- `patch_diagnostics/camera_coverage.csv` and `patch_diagnostics/generation.log`
  are mandatory for valid generated patches because they provide auditable
  camera-selection evidence.
- Diagnostic plots `plot.png`, `plot.html`, and `histogram.png` are
  expected where possible, but plot export failures
  are non-critical.
- `splat/patches/patch_summary.png` is expected after patch generation and must
  show all camera positions colour-coded by camera source plus all patch
  boundaries.
- `camera_coverage.csv` must include Feature 006 selection fields:
  `patch_id`, `image_id`, `image_name`, `selection_role`, `pool`,
  `source_patch`, `selection_reason`, `rejection_reason`, `hybrid_body_score`,
  `hybrid_boundary_score`, `track_body_score`, `track_boundary_score`,
  `projection_body_score`, `projection_boundary_score`, `target_image_share`,
  `new_body_sample_gain`, `new_boundary_sample_gain`, `new_local_cell_gain`,
  `view_bin_gain`, `nonlocal_penalty`, `spillover_penalty`, `warning_flags`,
  `camera_x`, `camera_y`, and `camera_z`.
- Non-critical diagnostic failures are recorded in `generation.log` and warning
  records but do not invalidate a patch with valid sparse data, selected images,
  metadata, and required audit table/log.

## Patch Metadata Required Fields

```json
{
  "patch_id": "p000",
  "source_run_id": "<run_id>",
  "source_sparse": "sfm/undistorted/sparse/0",
  "patch_affecting_config": {},
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
  "sparse_point_count": 0,
  "selector": {
    "name": "target_aware_spatial_greedy",
    "version": "1",
    "signature": "<stable selector-affecting signature>",
    "coverage": {},
    "warning_thresholds": {},
    "warning_flags": []
  },
  "invalid_reasons": [],
  "status": "valid",
  "warnings": []
}
```

Validation rules:
- `patch_id` must be unique.
- `bounds` must contain numeric `min_x`, `max_x`, `min_y`, `max_y`, `min_z`,
  `max_z`, and `buffer` values.
- `selected_images` must match images available in `selected_images/`.
- `selected_camera_count` must not exceed `patching.max_cameras`.
- `selector.name` must be `target_aware_spatial_greedy`, and selector
  `version`, `signature`, `coverage`, and `warning_thresholds` are required for
  reuse safety.
- `sparse_point_count` must be greater than zero for a valid patch.
- `status=invalid` patches are not sent to LFS.
