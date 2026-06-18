# Contract: Camera Selection V3 Config And Diagnostics

## Config

Public config path:

```yaml
advanced:
  splat:
    patching:
      max_cameras: 400
      external_support_fraction: 0.10
```

Rules:

- `max_cameras` is the final hard cap.
- `external_support_fraction` defaults to `0.10`.
- `external_support_fraction: 0` disables external support.
- Only `external_support_fraction` is swept for first V3 validation.

Derived values:

```text
external_support_allowance = floor(max_cameras * external_support_fraction)
internal_patch_target = max_cameras - external_support_allowance
```

## Patch Metadata

Required selector fields under `patch_metadata.json["selector"]`:

```json
{
  "name": "camera_selection_v3",
  "version": "v3",
  "signature": {
    "candidate_pool": "internal_plus_one_ring_neighbours",
    "signals": ["patch_tracks_seen", "footprint_overlap", "target_image_share"],
    "footprint_geometry": "image_corner_frustum_intersected_with_patch_rectangle_on_patch_median_z_plane",
    "target_image_geometry": "project_patch_frustum_intersection_polygon_to_image",
    "external_support_fraction": 0.1,
    "min_target_image_share": 0.05
  },
  "coverage": {
    "selected_internal_count": 0,
    "rejected_internal_count": 0,
    "selected_external_count": 0,
    "unused_external_count": 0
  },
  "warning_thresholds": {
    "min_target_image_share": 0.05,
    "near_min_target_image_share_margin": 0.01,
    "low_patch_footprint_coverage": 0.25
  },
  "warning_flags": []
}
```

## `camera_coverage.csv`

Required columns:

```text
image_name
selection_role
pool
source_patch
visible_patch_track_count
normalised_track_score
footprint_overlap_score
target_image_share
external_evidence_score
azimuth_degrees
azimuth_spread_score
external_score
camera_x
camera_y
camera_z
```

Column meanings:

- `visible_patch_track_count` comes from COLMAP sparse tracks inside the patch rectangle.
- `footprint_overlap_score` comes from the camera frustum footprint intersected with the full patch rectangle on an XY-parallel plane at the median Z of sparse points inside the patch.
- `target_image_share` comes from projecting that intersection polygon into the image.
- Sparse-point hulls or bounding boxes are not used for `footprint_overlap_score` or `target_image_share`.

Allowed `selection_role` values:

- `kept_internal`
- `rejected_internal`
- `selected_external`
- `unused_external`

## `generation.log`

Required lines:

```text
patch_id: p000
max_cameras: 400
external_support_fraction: 0.10
external_support_allowance: 40
internal_patch_target: 360
selected_internal_count: 0
rejected_internal_count: 0
selected_external_count: 0
unused_external_count: 0
```

Warnings use one line per warning:

```text
warning: <message>
```

## Validation Sweep Output

Folder shape:

```text
scratch/camera_selection_v3_pngs_<timestamp>/
├── dataset1_400_support005/
├── dataset1_400_support010/
├── dataset1_400_support015/
├── dataset2_400_support005/
├── dataset2_400_support010/
├── dataset2_400_support015/
├── summary.csv
└── review_notes.md
```

Each dataset/support folder contains only files named:

```text
pNNN_camera_selection.png
```
