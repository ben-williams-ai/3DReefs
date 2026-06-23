# Data Model: COLMAP SfM Pipeline

## PipelineConfig Extensions

Feature 2 extends the Feature 1 config with SfM settings under `advanced.sfm`
and a mandatory vocabulary-tree resource under `tools`.

Fields added or extended:
- `tools.vocab_tree_path`: path or command-like string to a local vocabulary tree
  file. Required whenever the selected matching mode uses vocabulary-tree
  retrieval.
- `advanced.sfm`: all non-mandatory SfM settings.

Validation rules:
- Public example configs use placeholders, not private paths.
- Unknown keys still fail through the existing config loader.
- Relative project-local paths resolve under `project.dir` only where the config
  contract states they are project-local.

## SfMConfig

Represents all user-configurable SfM behaviour.

Fields:
- `camera_config`: inferred or explicit camera layout/mapping controls.
- `preflight`: image, camera metadata, EXIF, GPU-support, and proceed-policy
  switches.
- `intrinsics`: camera model, pre-calculation, user camera file, and refinement
  settings.
- `feature_extraction`: feature image size, feature count, GPU, and SIFT
  settings.
- `matching`: selected matching mode plus matcher-specific settings.
- `reconstruction`: global/incremental backend and reconstruction options.
- `undistortion`: output size and source-image selection behaviour.
- `dense`: dense point cloud and mesh enablement/settings.

Validation rules:
- `matching.mode=sequential_vocab_tree` is the default.
- Matching modes that include vocabulary-tree retrieval require
  `tools.vocab_tree_path`.
- `reconstruction.backend` is either `global` or `incremental`.
- Mesh cannot be enabled unless dense output is enabled.
- No legacy standalone GLOMAP backend value is valid.

## ImageCollection

Represents discovered raw project images.

Fields:
- `root`: raw image root.
- `layout`: `single_camera` or `multi_camera`.
- `camera_groups`: list of camera groups.
- `total_images`: total supported image files.

Validation rules:
- Direct images and camera subfolders must not be mixed.
- Each camera group must contain at least one supported image.
- Raw images are read-only and never modified in place.

## CameraGroup

Represents one inferred or explicitly mapped camera.

Fields:
- `name`: camera folder name or generated single-camera name.
- `relative_root`: path relative to `raw_images`.
- `image_count`: number of supported images.
- `dimensions`: detected image dimensions and counts.
- `metadata_consistency`: `consistent`, `mixed`, or `unknown`.
- `metadata_examples`: small set of representative metadata/source examples.

Validation rules:
- More than one dimension in a camera group fails before heavy SfM work.
- `mixed` metadata consistency triggers an up-front decision.
- `unknown` metadata consistency is reported but does not fail by itself.

## RecolouredImageCollection

Represents optional recoloured inputs for later splatting-stage appearance handoff. These images are not SfM or COLMAP undistortion inputs.

Fields:
- `root`: recoloured image root.
- `mirrors_raw`: boolean.
- `missing_from_recoloured`: raw images without recoloured counterparts.
- `extra_recoloured`: recoloured images without raw counterparts.
- `dimension_mismatches`: matching filenames with different dimensions.

Validation rules:
- Required only when `project.recolour_images=true`.
- Must mirror raw relative paths and filenames exactly.
- Must match raw dimensions.
- Any mismatch fails before heavy SfM work.

## IntrinsicsSelection

Represents the chosen intrinsics source.

Fields:
- `source`: `precalculated` or `user_cameras_file`.
- `camera_model`: selected model when not overridden by camera file.
- `selected_images`: per-camera list used for pre-calculation.
- `warnings`: short sequence-size or validation warnings.
- `user_cameras_file`: optional path to user camera file.

Validation rules:
- User camera file must be parseable as COLMAP `cameras.txt`.
- Camera count must match camera groups.
- Camera dimensions must match raw image dimensions.
- User camera file disables pre-calculation and default model selection.

## MatchingStrategy

Represents the selected matching mode and ordered passes.

Fields:
- `mode`: one of `exhaustive`, `sequential`, `vocab_tree`, `spatial`,
  `sequential_vocab_tree`, `hybrid`.
- `passes`: ordered matcher pass names.
- `requires_vocab_tree`: boolean.
- `requires_pose_priors`: boolean.

Validation rules:
- `sequential_vocab_tree` resolves to sequential then vocabulary-tree passes.
- Spatial matching requires valid pose-prior support.
- Required resources must be present before matching starts.

## SfMRunState

Represents the stage state for one SfM invocation.

Fields:
- `database_path`
- `raw_sparse_root`
- `selected_sparse_model`
- `undistorted_root`
- `dense_root`
- `completed_stages`
- `partial_stages`
- `stage_decisions`

State transitions:
- `preflight_pending` -> `preflight_passed`
- `preflight_passed` -> `intrinsics_complete`
- `intrinsics_complete` -> `features_complete`
- `features_complete` -> `matching_complete`
- `matching_complete` -> `reconstruction_complete`
- `reconstruction_complete` -> `undistortion_complete`
- `undistortion_complete` -> `dense_complete` when dense is enabled
- `dense_complete` -> `mesh_complete` when mesh is enabled
- any stage -> `failed_partial` on failure after output creation

Validation rules:
- Prior partial or completed stages require decisions before execution.
- Config differences are evaluated before execution.
- Non-interactive runs fail when decisions are required and no explicit policy is
  supplied.

## SparseModelSummary

Represents one sparse model produced by reconstruction.

Fields:
- `model_id`: directory/model identifier.
- `path`: model path.
- `registered_images`: registered image count.
- `points3d`: 3D point count.
- `selected`: boolean.

Validation rules:
- The selected model is the model with the highest `registered_images`.
- Ties should be resolved deterministically and recorded in the run manifest.
- All model summaries are recorded when more than one model exists.

## SfMOutput

Represents outputs handed to later stages.

Fields:
- `sparse_model`: raw sparse selected model.
- `undistorted_images`: undistorted image directory.
- `undistorted_sparse`: undistorted sparse model directory.
- `undistorted_intrinsics`: cameras/intrinsics from undistorted sparse output.
- `dense_point_cloud`: optional path.
- `mesh`: optional path.

Validation rules:
- Downstream splatting uses `undistorted_images` and `undistorted_sparse`.
- Downstream stages must not use the original raw sparse intrinsics.
