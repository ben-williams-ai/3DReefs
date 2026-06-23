# Data Model: Optional Image Recolour Workflow

## ImageSequence

Represents the ordered source image set used by sequence-sensitive behaviours.

**Fields**:
- `source_root`: raw image root path.
- `items`: ordered `ImageItem` entries.
- `ordering_method`: `capture_metadata` or `natural_path`.
- `ordering_warnings`: warnings for missing, duplicate, or inconsistent metadata.
- `camera_groups`: ordered camera group names.

**Validation rules**:
- Every item path is relative to `source_root`.
- Ordering is stable and deterministic.
- Natural ordering is used when capture metadata is unavailable or unreliable.

## ImageItem

Represents one source image and its output identity.

**Fields**:
- `relative_path`: exact relative image path, including camera folder when present.
- `camera_group`: camera folder name, or `single`.
- `global_index`: zero-based index in the global ordered sequence.
- `camera_index`: zero-based index within the camera group.
- `capture_timestamp`: optional capture timestamp used for ordering.
- `width`, `height`: dimensions when known.

**Validation rules**:
- `relative_path` is unique within an `ImageSequence`.
- `camera_group` matches the top-level folder for multi-camera datasets.
- Output images must preserve `relative_path`, dimensions, and extension where possible.

## CameraGroup

Represents a top-level camera folder or the single-camera dataset group.

**Fields**:
- `name`: group name.
- `items`: ordered `ImageItem` entries for that camera.
- `keyframes`: selected keyframes for per-camera mode.

**Validation rules**:
- A multi-camera group must map to exactly one folder identity.
- Per-camera interpolation cannot use keyframes from another group.

## ColourParameterSet

Represents one complete Wildflow-style colour adjustment.

**Fields**:
- `gray_world`: numeric, neutral/off `0.0`.
- `warmth`: numeric, neutral `0.0`.
- `tint`: numeric, neutral `0.0`.
- `saturation`: numeric, neutral `1.0`.
- `blue_reduction`: numeric, off `0.0`.
- `brightness`: numeric, neutral `0.0`.
- `contrast`: numeric, neutral `0.0`.
- `shadows`: numeric, off `0.0`.
- `blacks`: numeric, off `0.0`.
- `highlights`: numeric, off `0.0`.
- `dehaze_strength`: numeric, off `0.0`.
- `dehaze_omega`: numeric, default `0.9`.

**Validation rules**:
- All fields are present.
- GUI controls must not artificially restrict ranges beyond the Wildflow source behaviour.
- Filters are applied in the Wildflow order: grey-world, warmth, tint, saturation, blue reduction, brightness/contrast, shadows, blacks, highlights, dehaze.

## Keyframe

Represents an image selected for manual tuning.

**Fields**:
- `id`: stable keyframe identifier based on relative path and mode scope.
- `relative_path`: source image relative path.
- `camera_group`: camera group name.
- `global_position`: one-based display position in the global sequence.
- `camera_position`: one-based display position in the camera group.
- `list_index`: one-based display row after current ordering.
- `parameters`: optional `ColourParameterSet`.
- `edited`: boolean.
- `thumbnail_path`: optional thumbnail/cache path.

**Validation rules**:
- Edited keyframes retain parameters when keyframes are rebuilt if the referenced image remains valid.
- Deleting a keyframe requires confirmation and immediate state save.
- Rebuilt rows must have unique, consecutive display indices.

## ColourRestorationState

Persistent state for one run's colour restoration workflow.

**Fields**:
- `schema_version`: state schema version.
- `run_id`: run identifier.
- `status`: `incomplete`, `active`, `applying`, `complete`, `skipped`, `cancelled`, or `failed`.
- `active_session`: whether a GUI or standalone session is active.
- `mode`: `global` or `per_camera`.
- `keyframe_count`: requested keyframe count.
- `ordering_method`: method used by `ImageSequence`.
- `source_raw_root`: raw image root.
- `output_recoloured_root`: corrected image root.
- `undistortion_source_sparse`: raw sparse model source for COLMAP undistortion.
- `final_undistorted_images`: raw-image COLMAP undistortion image path.
- `final_undistorted_sparse`: raw-image COLMAP undistortion sparse path.
- `splat_image_source`: `raw` or `recoloured`, selected after raw SfM/COLMAP undistortion.
- `keyframes`: selected `Keyframe` entries.
- `interpolation`: enough information to reproduce full-dataset parameter assignment.
- `relevant_config`: selected config values affecting colour restoration.
- `created_at`, `updated_at`: timestamps.
- `error`: optional failure details including failed image when applicable.

**State transitions**:
- `incomplete` -> `active` when GUI/session opens.
- `active` -> `applying` when full-dataset correction starts.
- `applying` -> `complete` after every corrected image is written and validated.
- `active` or `applying` -> `failed` when correction fails.
- `active` -> `skipped` when user continues without colour restoration.
- `active` -> `cancelled` when user cancels the job.
- `complete` -> `active` when user reopens for review/editing.

**Validation rules**:
- State is saved after every keyframe/state-changing action.
- `complete` requires all expected corrected images to exist with matching relative paths and dimensions.
- A `complete` state may adopt an existing project-level corrected image set when that set fully mirrors `raw_images/` with valid RGB images. Adopted states may not contain editable keyframes and record `adopted_existing_recoloured_images: true` in `relevant_config`.
- Reapply over existing corrected outputs requires explicit warning/confirmation.
- Splatting is blocked while `active_session` is true or status is `active`, `applying`, `incomplete`, or `failed`.

## CorrectedImageSet

Represents the mirrored corrected output tree.

**Fields**:
- `root`: corrected image root.
- `source_root`: raw image root.
- `items`: corrected images keyed by source relative path.
- `last_applied_at`: timestamp.
- `source_state_id`: state/checksum identifier for reproducibility.

**Validation rules**:
- Contains exactly one corrected output for every source image.
- Does not contain extra image paths.
- Preserves image dimensions, relative paths, filenames, and extension where possible.
- JPEG outputs use high-quality lossy saving.
- A complete project-level set may be reused across experiment runs for the same dataset without re-running colour restoration.

## SplatInputHandoff

Represents the downstream inputs consumed by splatting.

**Fields**:
- `geometry_images_path`: `sfm/undistorted/images`, always produced from raw images by COLMAP undistortion.
- `sparse_path`: `sfm/undistorted/sparse`, always produced from raw-image SfM geometry.
- `splat_image_source`: `raw` or `recoloured`.
- `splat_images_path`: raw-image path when colour restoration is disabled/skipped, or `CorrectedImageSet.root` when complete colour restoration is selected for splatting.
- `source_reconstruction`: raw-image SfM reconstruction used for geometry.

**Validation rules**:
- SfM feature extraction, matching, reconstruction, and COLMAP undistortion always use raw images.
- When colour restoration is disabled or skipped, splatting image inputs match the current raw-image pipeline.
- When colour restoration is enabled and complete, only splatting-stage image inputs may derive from `CorrectedImageSet`.
- Sparse model and image names remain consistent with the raw-image reconstruction.
