# Contract: Patch Selection Artefacts

Patch metadata must include selector provenance and summary counts.

Required `patch_metadata.json` fields:

```json
{
  "patch_id": "p000",
  "bounds": {
    "min_x": 0.0,
    "max_x": 1.0,
    "min_y": 0.0,
    "max_y": 1.0,
    "min_z": -1.0,
    "max_z": 1.0,
    "buffer": 0.1
  },
  "selected_images": [],
  "selected_camera_count": 0,
  "selected_internal_count": 0,
  "selected_external_count": 0,
  "selector": {
    "name": "camera_selection_v2",
    "version": "3",
    "signature": "<stable selector-affecting signature>",
    "scene_registered_image_count": 0,
    "scene_target_cell_count": 0,
    "patch_target_cell_count": 0,
    "grid_x_count": 0,
    "grid_y_count": 0,
    "coverage": {
      "footprint": 0.0,
      "internal_camera_cells": 0.0,
      "view_direction_bins": 0.0
    },
    "target_image_share": {
      "median_selected": 0.0,
      "min_selected": 0.0
    },
    "warnings": []
  }
}
```

Rules:

- `selector.name` and `selector.version` identify this feature's selector.
- The selector must not write a legacy selector-mode field.
- Selected camera count must not exceed `patching.max_cameras`.
- Existing outputs with incompatible selector signature require up-front reuse or
  overwrite decision.
- Warning-only weak coverage does not invalidate a patch.
