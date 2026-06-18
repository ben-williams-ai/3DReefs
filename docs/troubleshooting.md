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

## 2026-06-15 - Post-Processing Tool Fails Preflight

- Branch: `005-splat-post-processing`
- Error or symptom: `splat.cleanup`, `splat.merge`, `splat.sog`, or `splat.postprocess` fails before any post-processing command runs.
- Context or command: Running post-processing on an existing trained splat run.
- Likely cause: Wildflow is missing required cleanup/merge functions, `splat-transform` is missing, or `splat-transform --help` does not show support for SOG output.
- Fix or workaround: Install `wildflow>=0.1.5`, check `tools.splat_transform_bin`, run `splat-transform --version` and `splat-transform --help`, or disable the requested post-processing stage until the toolchain is installed.

## 2026-06-15 - SOG Export Fails After Merge

- Branch: `005-splat-post-processing`
- Error or symptom: `postprocess_manifest.json` reports `status: partial`, with a valid `splat/merged/merged_splat.ply` but failed final SOG output.
- Context or command: `uv run main.py --config <config.yml> --run-id <run_id> --steps splat.postprocess`.
- Likely cause: The final `splat-transform` SOG export failed after the cleaned merged PLY was already written.
- Fix or workaround: Inspect `logs/splat_transform.log`, keep the merged PLY as the valid site-level splat, then rerun only `--steps splat.sog --resume-policy overwrite` after fixing the conversion issue.

## 2026-06-15 - Merge Has Missing Or Excluded Patches

- Branch: `005-splat-post-processing`
- Error or symptom: The final merged PLY exists but warnings list excluded cleaned patches or severely incomplete patch sources.
- Context or command: `splat.merge` or `splat.postprocess`.
- Likely cause: One or more patches lacked a cleaned output, cleanup failed, or only an incomplete training output was available.
- Fix or workaround: Review `splat/postprocess/postprocess_manifest.json`; rerun the affected patch training or cleanup stage if the missing area matters, then rerun merge and SOG.

## 2026-06-15 - Jagged Or Faded Patch Borders After Cleanup

- Branch: `005-splat-post-processing`
- Error or symptom: Cleaned patch splats still show messy, faded, or jagged edge overlap instead of sharp trimmed patch boundaries.
- Context or command: `splat.postprocess` on Feature 3 patch outputs whose `patch_metadata.json` stores bounds inside a nested `bounds` object.
- Likely cause: Boundary filtering was enabled, but cleanup was reading only the old top-level `min_x`, `max_x`, `min_y`, `max_y`, `min_z`, and `max_z` metadata shape, so wildflow received no spatial boundary parameters.
- Fix or workaround: Patch generation now writes canonical nested `bounds`, and cleanup requires that shape. Regenerate patches before rerunning `--steps splat.postprocess --resume-policy overwrite` so cleaned patch PLYs, merged PLY, and final SOG use proper boundary trimming.

## 2026-06-15 - LFS Bucket-Buffer OOM During Boundary Rebuild Trial

- Branch: `005-splat-post-processing`
- Error or symptom: LFS reports `OUT_OF_MEMORY: Failed to allocate bucket buffers`, switches tile modes, then can fail at maximum tile mode despite GPU VRAM not being near capacity.
- Context or command: Dataset 1 boundary-rebuild trial for patches `p000` and `p001` using `--max-cap 1500000`.
- Likely cause: LFS internal tile/bucket allocation pressure, not true RTX 6000 Ada capacity exhaustion. The trial also used the old 1.5M cap rather than the current Dataset 1 1.0M config.
- Fix or workaround: Rerun the trial with an explicit `--advanced.splat.train.num_splats_per_patch 1000000` override so the run record is unambiguous. Patches `p000` and `p001` then completed at 30,000 iterations and 1,000,000 splats. If bucket-buffer OOM persists on other patches, try the old LFS `increase_init_scaling` config profile or reduce the per-patch splat cap for the inspection trial.

## 2026-06-15 - COLMAP Text Image Counting Included Observation Lines

- Branch: `005-splat-post-processing`
- Error or symptom: Sparse model summaries reported too many registered images after test fixtures gained realistic image observation lines.
- Context or command: `uv run pytest -q` after restoring old-style view-based patch camera selection.
- Likely cause: The text sparse summary counted any non-comment line beginning with a number in `images.txt`, including the 2D observation line below each registered image header.
- Fix or workaround: Count only real COLMAP image header lines with quaternion, translation, camera id, and image name fields.

## 2026-06-18 - Useful Internal Camera Count Exceeds Final Cap

- Branch: `009-camera-selection-v3`
- Error or symptom: Camera Selection V3 raises a patch-bound sizing invariant error because useful internal cameras exceed `max_cameras`.
- Context or command: `uv run main.py --config <config.yml> --steps splat.patch`
- Likely cause: Patch bounds were not generated with the internal camera target, or the patch geometry grouped too many useful internal cameras into one patch.
- Fix or workaround: Regenerate patch bounds using `internal_patch_target = max_cameras - floor(max_cameras * external_support_fraction)`. If it persists, lower `max_cameras`, lower `external_support_fraction`, or inspect wildflow patch generation for that scene.

## 2026-06-16 - Patch-Specific LFS Retry Must Not Overwrite Other Patches

- Branch: `006-hybrid-camera-selection`
- Error or symptom: Dataset 1 hybrid comparison patch `p000` hit LFS `OUT_OF_MEMORY: Failed to allocate bucket buffers` at 12,900/30,000 iterations with a 1,000,000 splat cap, while total GPU VRAM was not near capacity.
- Context or command: `tmux` session `reefs_hybrid_splat_compare`, run `hybrid_20260616T193205Z_dataset1_patch400_1m`, using `--steps splat,splat.postprocess`.
- Likely cause: LFS internal bucket/tile allocation pressure on one patch, not whole-GPU exhaustion. A separate safety bug meant targeted repair commands with `--advanced.splat.train.patch_ids` could still discover all patch `splat/` folders as existing outputs.
- Fix or workaround: Existing-output discovery for `splat.train` now respects requested training patch IDs, so a later targeted retry can overwrite only the failed patch. The old `increase_init_scaling` LFS profile made the Dataset 1 `p000` case fail earlier, so do not use it as the default retry. The practical stabilisation was adding the optional LFS `--max-width` config and setting `advanced.splat.train.max_width: 1024` for the hybrid comparison runs; `2048` still failed on `p000`, while `1024` completed 30,000 iterations with 1,000,000 splats.

## 2026-06-17 - Hybrid Selector Patch Generation Is CPU-Heavy

- Branch: `006-hybrid-camera-selection`
- Error or symptom: Hybrid camera-selection patch generation is much slower than LFS training on large completed SfM runs, especially Dataset 2.
- Context or command: `scratch/run_hybrid_splat_comparison.sh 20260616T232624Z` generated new 400- and 800-camera comparison runs for Dataset 1 and Dataset 2.
- Likely cause: The target-aware selector projects target samples into all registered cameras for each patch, then fuses that with sparse-track evidence. This is the intended behaviour, but the current implementation is pure Python and does not cache or pre-prune projection candidates aggressively.
- Fix or workaround: The final comparison completed successfully, so this is a performance issue rather than a correctness bug. Future optimisation should preserve the single selector behaviour while caching per-camera projection data or narrowing geometric projection candidates before scoring every camera for every patch.

## 2026-06-17 - LFS v0.5.2 FastGS Bucket-Buffer OOM

- Branch: `006-hybrid-camera-selection`
- Error or symptom: Full-width MCMC training can fail with `OUT_OF_MEMORY: Failed to allocate bucket buffers` after LFS switches tile mode from 1 to 2 to 4, even when total RTX 6000 Ada VRAM is not close to exhausted.
- Context or command: Dataset 1 hybrid comparison full-width patch training with LFS `v0.5.2`, `--strategy mcmc`, and `--max-cap 1000000`.
- Likely cause: This is the LFS FastGS training rasteriser's internal bucket-buffer allocation path, not ordinary whole-card VRAM exhaustion. The installed `v0.5.2` tag includes the Apr 2026 `#1055` overflow fix, but not later May 2026 upstream master commits that harden FastGS further and remove the failing bucket-buffer path.
- Fix or workaround: Use a post-`v0.5.2` LichtFeld Studio build pinned at upstream commit `6d591a34` or later, and point local `.env` `LFS_BIN` at that binary. Known failing full-width MCMC patches `p000`, `p003`, and retry `p001` all completed 30,000/30,000 iterations with 1,000,000 splats on commit `6d591a34`; peak VRAM stayed around 12-15 GB. Treat `max_width: 1024` as a temporary comparison-run workaround only, not the preferred production fix.

## 2026-06-17 - Do Not Hardlink Whole Run Directories

- Branch: `008-camera-selection-v2`
- Error or symptom: New comparison run folders appeared to share `run_status.json`, logs, and other mutable records with the canonical SfM run.
- Context or command: Creating Camera Selection V2 comparison runs from an existing completed SfM run using `cp -al`.
- Likely cause: Hardlinking the whole run directory also hardlinked mutable files. Updating one run's status/logs then changed the source run and sibling comparison runs.
- Fix or workaround: Only reuse immutable heavy SfM artefacts by symlink or normal copy. Mutable run records, logs, and `splat/` outputs must be separate files per run. The affected partial comparison attempts were archived under `scratch/archived_dataset_runs_20260617T183541Z_camera_selection_v2/failed_hardlink_attempts`, and the canonical Dataset 1/2 runs were reset to SfM-only status.
