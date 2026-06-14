# Troubleshooting

## 2026-06-10 - Invalid Config

- Branch: `001-pipeline-foundation`
- Error or symptom: The CLI exits before creating a run directory.
- Context or command: `uv run main.py --config <config.yml>`
- Likely cause: Missing required config keys, malformed YAML, wrong value types, or unknown dotted CLI overrides.
- Fix or workaround: Validate the config against `configs/example.yml`; correct unknown override keys before rerunning.

## 2026-06-10 - Ambiguous Image Layout

- Branch: `001-pipeline-foundation`
- Error or symptom: `raw_images mixes direct images and camera subfolders`.
- Context or command: Foundation preflight during image layout validation.
- Likely cause: `raw_images/` contains both direct image files and camera folders.
- Fix or workaround: For single-camera data, place images directly in `raw_images/`. For multi-camera data, place images inside `raw_images/cam1/`, `raw_images/cam2/`, and so on.

## 2026-06-10 - Missing External Tool

- Branch: `001-pipeline-foundation`
- Error or symptom: Tool validation fails for COLMAP, LichtFeld Studio, or `splat-transform`.
- Context or command: Foundation preflight validates only bounded version/help commands.
- Likely cause: The configured binary is not on `PATH`, points to the wrong executable, or reports an unsupported version.
- Fix or workaround: Update the local config `tools.*_bin` value or install the expected tool version.

## 2026-06-10 - Partial-Run Conflict

- Branch: `001-pipeline-foundation`
- Error or symptom: Non-interactive runs fail with a required resume/overwrite decision.
- Context or command: Re-running a project with prior partial outputs.
- Likely cause: The pipeline found uncertain prior outputs and cannot safely continue without explicit intent.
- Fix or workaround: Run interactively, or pass `--resume-policy resume`, `--resume-policy overwrite`, or `--resume-policy fail`.

## 2026-06-10 - Stale Placeholder SfM Steps In Foundation Tests

- Branch: `002-colmap-sfm-pipeline`
- Error or symptom: Foundation tests started failing with image-dimension or COLMAP-stage errors.
- Context or command: `uv run pytest tests/unit tests/integration`
- Likely cause: Feature 1 tests used `--steps sfm` as an inert placeholder, but Feature 2 makes `sfm` a real COLMAP pipeline step.
- Fix or workaround: Use `--steps foundation` or another non-SfM placeholder in foundation-only tests; use dedicated SfM tests for `--steps sfm`.

## 2026-06-10 - Intrinsics Selection Without Actual Pre-Calculation

- Branch: `002-colmap-sfm-pipeline`
- Error or symptom: A smoke run completed, but the main feature extraction used only COLMAP's default focal prior instead of estimated camera parameters.
- Context or command: First local `uv run main.py --config configs/test.yml --steps sfm --resume-policy overwrite` smoke run.
- Likely cause: The implementation recorded selected calibration images but did not yet run a subset calibration stage.
- Fix or workaround: Add `sfm.intrinsics.*` stages that reconstruct a selected-image subset, export `cameras.txt`, and pass `--ImageReader.camera_params` into the full feature extraction.

## 2026-06-10 - Vocabulary Tree Required For Default SfM Matching

- Branch: `002-colmap-sfm-pipeline`
- Error or symptom: SfM preflight fails with `Selected SfM matching mode requires a valid tools.vocab_tree_path`.
- Context or command: `uv run main.py --config <config.yml> --steps sfm`
- Likely cause: The default matching mode runs sequential matching plus vocabulary-tree matching, and no valid vocabulary tree file is configured.
- Fix or workaround: Download a COLMAP-compatible vocabulary tree and set `tools.vocab_tree_path` in a local config, or choose a matching mode that does not use vocabulary-tree retrieval.

## 2026-06-11 - Interrupted SfM Run Missing Final Records

- Branch: `004-run-resume-hardening`
- Error or symptom: A large SfM run has substantial `sfm/` outputs but lacks final `run_manifest.json`, `run_status.json`, or `timings.json`, or the active COLMAP command lacks an exit-code tail in `logs/colmap.log`.
- Context or command: Long `uv run main.py --config <dataset-config> --steps sfm` runs interrupted during a COLMAP substage such as `sfm.undistort`.
- Likely cause: The host process or terminal session stopped before the old end-of-run record writer executed.
- Fix or workaround: Use the hardened CLI with `--run-id <existing-run-id> --steps <stage> --resume-policy overwrite` or `resume`. The pipeline now writes records at run start, updates each stage, and inspects filesystem outputs when older records are missing.

## 2026-06-11 - Splat Command Cannot Find Undistorted SfM Outputs

- Branch: `003-splat-patching-training`
- Error or symptom: `COLMAP undistorted images directory is missing`.
- Context or command: Running `uv run main.py --config <config.yml> --steps splat.patch` without selecting an existing SfM run.
- Likely cause: A fresh run directory was created for the splat-only command, so it does not contain `sfm/undistorted/` outputs.
- Fix or workaround: Pass `--run-id <sfm_run_id>` for the completed SfM run, or run splat stages as part of a future end-to-end command that has just produced SfM outputs in the same run directory.

## 2026-06-11 - Binary COLMAP Sparse Output During Patching

- Branch: `003-splat-patching-training`
- Error or symptom: Patch planning cannot read camera names, poses, or tracks from `sfm/undistorted/sparse`.
- Context or command: `splat.patch` after COLMAP undistortion, which often writes `cameras.bin`, `images.bin`, and `points3D.bin`.
- Likely cause: Patch generation needs text-readable sparse data for diagnostics and deterministic selection.
- Fix or workaround: The pipeline now exports a text copy under `splat/source_sparse_txt/` using `pycolmap`. If this fails, check that `pycolmap` can read the source sparse model.

## 2026-06-11 - Resumed Splat Run Marks Completed Undistortion As Partial

- Branch: `003-splat-patching-training`
- Error or symptom: A completed resumed splat run showed `stage_statuses.sfm.undistort: partial` even though `sfm/undistorted/images` and `sfm/undistorted/sparse` were usable.
- Context or command: `uv run main.py --config configs/datasets/dataset_01.yml --run-id 2026-06-11T094353.180835+0000 --steps splat --resume-policy overwrite`
- Likely cause: Filesystem recovery compared the undistorted image count against the pre-undistortion selected sparse count. COLMAP undistortion may output a slightly different registered-image set, and binary sparse summaries only prove file presence unless converted.
- Fix or workaround: Recovery now prefers the undistorted sparse/image outputs when checking `sfm.undistort`. For binary-only sparse outputs with a non-empty image directory, the undistorted image count is used as the recoverable completion count.

## 2026-06-11 - Dataset 1 Full Splat Training Smoke

- Branch: `003-splat-patching-training`
- Error or symptom: First full large splat run needed validation for patch size, memory use, and long-job resilience.
- Context or command: Dataset 1 splat run in `tmux` session `reefs_dataset1_splat`, using `--steps splat`, `--run-id 2026-06-11T094353.180835+0000`, and `--resume-policy overwrite`.
- Likely cause: This was the first run with 8,774 undistorted images and 11 large LFS patches at `advanced.splat.patching.max_cameras: 800`.
- Fix or workaround: Patch size 800 completed on the RTX 6000 Ada without OOM. The run produced 11 complete patch splats at 30,000 iterations and 1,500,000 splats each. Use `tmux` plus run logs for future long runs; inspect `logs/lfs.log`, `splat/training/training_manifest.json`, and each patch's `training_status.json`.

## 2026-06-12 - Binary Sparse Summaries Show Placeholder Counts

- Branch: `003-splat-patching-training`
- Error or symptom: A splat preflight manifest can show `registered_images: 1` and `points3d: 1` for a valid binary COLMAP sparse model.
- Context or command: Full Dataset 2 run reached splat preflight after COLMAP undistortion wrote binary sparse files.
- Likely cause: The sparse summary helper used `1` as a conservative non-empty binary-file marker when text sparse files were unavailable.
- Fix or workaround: The helper now uses `pycolmap` to read exact binary sparse counts when possible, falling back to the non-empty marker only if exact reading fails. The Dataset 2 run manifest was updated to show the correct 6,590 registered images and 3,185,852 points.
