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
    selection_plot.png
    selection_plot.html
    coverage_histogram.png
    generation.log
  splat/
```

Required behaviour:
- `patch_metadata.json` is mandatory.
- `sparse/0/` is mandatory for valid patches.
- `selected_images/` must expose only images selected for that patch, preferably
  via symlinks to undistorted images.
- `patch_diagnostics/` is written for every patch where possible.
- Non-critical diagnostic failures are recorded in `generation.log` and warning
  records but do not invalidate a patch with valid sparse data and selected
  images.

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
  "status": "valid",
  "warnings": []
}
```

Validation rules:
- `patch_id` must be unique.
- `selected_images` must match images available in `selected_images/`.
- `selected_camera_count` must not exceed `patching.max_cameras`.
- `status=invalid` patches are not sent to LFS.
