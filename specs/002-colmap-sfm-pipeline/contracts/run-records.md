# Run Record Contract: COLMAP SfM Pipeline

Feature 2 extends the Feature 1 run record under:

```text
<project.dir>/runs/<run_id>/
```

## Required Additional Files/Directories

```text
logs/
  colmap.log
sfm/
  database.db
  intrinsics_subset/
  sparse/
  selected_sparse/
  selected_sparse_txt/
  undistorted/
    images/
    sparse/
diagnostics/
  image_dimension_report.csv          # only when dimension issues/details exist
  camera_source_report.csv            # when metadata checks run
  intrinsics_selection.json           # when intrinsics pre-calculation runs
```

`diagnostics/` is created only when substantive diagnostic artefacts are written.

## Manifest Additions

`run_manifest.json` must include an `sfm` object after SfM stages run or are
reused.

Required fields:
- `database_path`
- `raw_sparse_root`
- `sparse_models`: list of `{model_id, path, registered_images, points3d, selected}`
- `selected_sparse_model`
- `undistorted_images`
- `undistorted_sparse`
- `undistorted_intrinsics`
- `undistortion_image_source`: `raw` or `recoloured`
- `intrinsics_camera_params`: present when default pre-calculation or a
  validated cameras file supplies fixed camera parameters
- `dense_point_cloud`: optional
- `mesh`: optional
- `stage_decisions`
- `warnings`

## Status Additions

`run_status.json` stage names may include:
- `sfm_preflight`
- `sfm_intrinsics`
- `sfm_feature_extraction`
- `sfm_matching_<mode_or_pass>`
- `sfm_reconstruction`
- `sfm_undistortion`
- `sfm_dense_patch_match`
- `sfm_dense_fusion`
- `sfm_mesh`

## Timings Additions

`timings.json` must record exact start/end/duration/status for every SfM stage
that runs or fails.

## Warning Events

Warnings may include:
- short intrinsics calibration image selection.
- mixed camera-source metadata confirmed by user.
- multiple sparse models produced.
- runtime GPU fallback warning detected after preflight expected GPU support.
- use of reused/resumed prior outputs.

Warnings must be visible in `logs/pipeline.log`; `logs/warnings.log` is created
only when warnings occur.
