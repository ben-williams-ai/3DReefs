# COLMAP Command Contract

This contract records intended command semantics. Exact option names must be
validated against COLMAP `4.0.4` help output during implementation.

## Feature Extraction

Command:

```text
colmap feature_extractor
```

Required inputs:
- run database path
- raw image path
- camera model or validated camera file-derived settings
- feature extraction settings from effective config

Required behaviour:
- Always uses raw images.
- Uses raw image dimensions when max image size is `null`.
- Applies protective feature-count reduction above 10000 images only when the
  user did not explicitly set a feature count.
- When default intrinsics pre-calculation is enabled, the full feature
  extraction receives `ImageReader.camera_params` estimated from the
  selected-image intrinsics subset.

## Intrinsics Pre-Calculation

Default behaviour:
- create a selected-image subset using the configured per-camera selection
  window.
- run COLMAP feature extraction, matching, and reconstruction on the subset.
- enable intrinsics refinement for the subset reconstruction.
- export the selected subset sparse model to text and read OPENCV camera
  parameters from `cameras.txt`.
- pass those parameters to the full raw-image feature extraction.
- keep final reconstruction intrinsics refinement disabled unless explicitly
  enabled.

## Matching

Supported pass commands:
- `exhaustive_matcher`
- `sequential_matcher`
- `vocab_tree_matcher`
- `spatial_matcher`

Named mode expansion:
- `exhaustive` -> exhaustive
- `sequential` -> sequential
- `vocab_tree` -> vocabulary-tree
- `spatial` -> spatial
- `sequential_vocab_tree` -> sequential, then vocabulary-tree
- `hybrid` -> named sequence defined in plan/tasks; must not be treated as a
  COLMAP command

Required behaviour:
- Matching consumes the feature database.
- Vocabulary-tree passes require `tools.vocab_tree_path`.
- Spatial passes require valid pose-prior support.
- Each pass has a separate timing entry.

## Reconstruction

Supported backends:
- `global` -> COLMAP `global_mapper`
- `incremental` -> COLMAP `mapper`

Required behaviour:
- Default backend is `global`.
- No fallback between backends.
- No legacy standalone GLOMAP command.
- Selected backend and options are recorded.

## Sparse Model Selection

After reconstruction:
- enumerate produced sparse models.
- count registered images and 3D points for each model.
- select the model with the highest registered image count.
- warn when more than one model exists.
- record all counts and selected model in manifest/status records.

## Undistortion

Command:

```text
colmap image_undistorter
```

Required inputs:
- selected sparse model path
- raw image root when `project.recolour_images=false`
- recoloured image root when `project.recolour_images=true`
- output path under the run's SfM output directory

Required behaviour:
- Run after sparse reconstruction.
- Maximum output dimension defaults to 4096, preserving aspect ratio and keeping
  smaller images unchanged.
- Downstream splatting uses undistorted images and undistorted sparse intrinsics.

## Dense And Mesh

Dense commands when enabled:
- `patch_match_stereo`
- `stereo_fusion`

Mesh command when enabled:
- `delaunay_mesher` by default
- `poisson_mesher` when `advanced.sfm.dense.mesh.method=poisson`

Required behaviour:
- Disabled by default.
- Mesh requires dense output.
- Timings, output paths, file sizes, and point/mesh summary data are recorded
  when available.
