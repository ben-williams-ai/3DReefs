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
- `undistortion_image_source`: `raw`
- `splat_image_source`: `raw` or `recoloured`
- `intrinsics_camera_params`: present when default pre-calculation or a
  validated cameras file supplies fixed camera parameters
- `dense_point_cloud`: optional
- `mesh`: optional
- `stage_decisions`
- `warnings`

## Status Additions

`run_status.json` stage names may include:
- `sfm.preflight`
- `sfm.intrinsics.*`
- `sfm.extract`
- `sfm.match.<mode_or_pass>`
- `sfm.reconstruct`
- `sfm.reconstruct.export_text`
- `sfm.undistort`
- `sfm.dense.patch_match`
- `sfm.dense.fusion`
- `sfm.mesh`

The status file MUST be written before each COLMAP substage starts and after it
finishes. A run interrupted during a COLMAP command should therefore show the
active or interrupted stage rather than only a missing final manifest.

## Timings Additions

`timings.json` must record exact start/end/duration/status for every SfM stage
that runs or fails.

`logs/colmap.log` must stream command output while commands run. It MUST include
the command line, start time, exit code, and duration where the process exits
normally. If the host kills the process, the log may lack a final exit code, but
the status file should still identify the active stage.

## Resume/Overwrite Recovery

When resuming with `--run-id`, SfM stages reuse outputs from the same run
directory. `sfm.undistort` MUST use the existing `sfm/selected_sparse/` from
that run. If `--resume-policy overwrite` is supplied for `sfm.undistort`, the
generated partial `sfm/undistorted/` output is removed before rerunning
COLMAP `image_undistorter`, and that removal is recorded in the manifest.

If canonical records are missing or incomplete, the pipeline MUST inspect
filesystem outputs such as the COLMAP database, selected sparse model, and
undistorted images to infer whether feature extraction, matching,
reconstruction, or undistortion is complete or partial.

Resume is supported at COLMAP stage boundaries, not inside a single COLMAP
subprocess. If a command is interrupted midway through `image_undistorter`,
the next run restarts `sfm.undistort` from the beginning after clearing partial
generated output. If sequential matching completed and vocabulary-tree matching
did not, the next run may request `sfm.match.vocab_tree` and reuse the existing
database written by feature extraction and earlier matching passes.

Supported explicit SfM resume/rerun boundaries include:
- `sfm.preflight`
- `sfm.extract` / `sfm.feature_extraction`
- `sfm.match.sequential`
- `sfm.match.vocab_tree`
- `sfm.match.exhaustive`
- `sfm.match.spatial`
- `sfm.reconstruct`
- `sfm.undistort`

## Warning Events

Warnings may include:
- short intrinsics calibration image selection.
- mixed camera-source metadata confirmed by user.
- multiple sparse models produced.
- runtime GPU fallback warning detected after preflight expected GPU support.
- use of reused/resumed prior outputs.

Warnings must be visible in `logs/pipeline.log`; `logs/warnings.log` is created
only when warnings occur.
