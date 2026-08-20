# Troubleshooting

## 2026-08-19 - Independent Boundary Insets Create Internal Model Holes

- Branch: `repair/gap-safe-models`
- Error or symptom: Complete neighbouring patches produce triangular or
  rectangular holes after post-processing; some healthy patches lose most of
  their Gaussians.
- Context or command: Production `splat.cleanup` with every patch cropped
  inward by `boundary_buffer: 0.1` before merge.
- Likely cause: Both sides of an internal overlap were independently removed.
  Keeping all overlap was messy, and nearest-centre ownership could select a
  patch with no Gaussian at the cell.
- Fix or workaround: Run Wildflow without patch boundary clipping, then trim
  only outside the union of every valid patch's unbuffered core footprint.
  This lets any neighbouring patch fill an internal join while preserving a
  hard outer scene perimeter.

## 2026-08-20 - Occupied-Cell Ownership Can Hide Thin Patch Joins

- Branch: `repair/gap-safe-models`
- Error or symptom: A coverage audit reports zero lost occupied cells, but a
  top-down render still has triangular internal gaps.
- Context or command: Dataset 6 after exclusive per-cell patch ownership and
  a 45-million-SOG delivery.
- Likely cause: The reference coverage was calculated after each source had
  already been clipped to its own rectangle, and one retained centre was
  treated as adequate surface density. Valid neighbour overlap was invisible
  to the audit.
- Fix or workaround: Build the reference from ordinary Wildflow outputs over
  the complete layout union. Preserve original Gaussian records during the
  45-million selection; pairwise decimation can enlarge scales and create
  perimeter spikes.

## 2026-07-23 - Stage 1 Timeout Plus False Success Deletes Failed VM

- Branch: `main`
- Error or symptom: A long SfM job reaches the 24-hour scientific timeout, records a failed row, but the pinned outer worker reports `PIPELINE_EXIT:0`; a launcher with `DELETE_ON_FINISH=true` then deletes the VM and its unuploaded database/model state.
- Context or command: All six Dataset 6 incremental variants timed out together during COLMAP mapping or bundle adjustment. Their S3 prefixes contain diagnostics but no database or sparse model.
- Likely cause: The fixed 86,400-second timeout was shorter than these reconstructions, and the caught-failure propagation bug made the launcher treat failure as verified success.
- Fix or workaround: Use the top-level failed-row propagation check, set a measured timeout above the expected mapper duration, and keep deletion gated on verified scientific rows plus durable artefact checks. For already-pinned long jobs, disable automatic deletion before the timeout rather than waiting for the first failure.

## 2026-07-23 - Stage 1 Scientific Failure Returned Outer Success

- Branch: `main`
- Error or symptom: A Stage 1 job records `status=failed` after SfM patch generation fails, but the ablation CLI and VM launcher exit zero and the VM can be deleted.
- Context or command: Dataset 6 `sfm_2048_sift_global`; Wildflow returned `No solution found`, while the outer ablation runner still returned success.
- Likely cause: The per-job runner deliberately catches exceptions to preserve failed ledger rows, but the top-level command did not check those rows before returning.
- Fix or workaround: The ablation runner now requires every requested scientific row to be complete before returning zero. Keep the launcher's remote `PIPELINE_EXIT/UPLOAD_STATUS` marker check as a second deletion gate.

## 2026-07-23 - Stage 1 Upload Followed Container-Only Symlinks

- Branch: `main`
- Error or symptom: Scientifically complete Stage 1 jobs finish with `PIPELINE_EXIT:0` and `UPLOAD_STATUS:1`; AWS CLI warns that generated evaluation image links do not exist.
- Context or command: Final host-side `aws s3 sync` of `ablation_eval` after full-resolution validation.
- Likely cause: AWS CLI follows local symlinks by default, while the generated links target paths that exist only inside the worker container.
- Fix or workaround: Use `--no-follow-symlinks` for host-to-S3 run and evaluation uploads. Upload the inner Stage 1 scientific run explicitly because its ID differs from the outer worker ID.

## 2026-07-23 - Validation Patch Has No Registered Internal Images

- Branch: `main`
- Error or symptom: Stage 1 validation stops at holdout creation with `patch has no registered internal images`.
- Context or command: Dataset 6 `sfm_full_sift_global`, selected patch `p022`.
- Likely cause: Spatial patch generation can emit a patch whose internal selected names have no intersection with its exported registered sparse images.
- Fix or workaround: Filter candidates with the same registered-internal-image check used by Stage 2 source layout generation, then select the requested evenly distributed validation patches from eligible candidates.

## 2026-07-06 - LFS Eval Config Must Start From Full Optimisation Defaults

- Branch: `main`
- Error or symptom: Validation splat rows fail almost immediately with `failure_reason=lfs_exit_1`; LFS logs show `Config load failed: Error parsing optimization parameters`.
- Context or command: Stage 1 ablation validation eval with `advanced.splat.train.lfs_config: null`.
- Likely cause: `null` should mean "use the normal packaged LFS optimisation defaults", but the eval writer created a tiny config containing only eval/save cadence fields and passed it to LFS with `--config`.
- Fix or workaround: `write_lfs_eval_config` now loads `/opt/lichtfeld-studio/eval/mcmc_optimization_params.json` when it is available and no explicit base config is set, then applies the eval/save cadence overrides. If this recurs, inspect the uploaded `ablation_eval/splat_eval/<run>/<patch>/attempt_*/lfs_eval_config.json` and `run.log`.

## 2026-07-05 - Stage 1 Ablation Drift Disabled Paired-Camera Matching

- Branch: `main`
- Error or symptom: Stage 1 ablation probe effective config shows `advanced.sfm.matching.cross_camera_pairs.enabled=true` but `advanced.sfm.matching.cross_camera_pairs.run_matching_pass=false`.
- Context or command: Canonical Stage 1 probes such as `sfm_dataset1_sfm_1024_sift_global` and `sfm_dataset2_sfm_1024_sift_global`.
- Likely cause: `experiments/ablations/ablation_config.yml` drifted from the dataset configs: it generated cross-camera pair files but did not run COLMAP `matches_importer`, so paired-camera candidates were not added to the matching database.
- Fix or workaround: Treat such runs as invalid for the AIMS baseline. The ablation baseline should match the dataset configs except for explicit sweep dimensions and path/runtime changes; verify `advanced.sfm.matching.cross_camera_pairs.run_matching_pass=true` before launching canonical Stage 1 jobs.

## 2026-06-25 - COLMAP Global Mapper cuDSS Failure Can Exit Cleanly

- Branch: `ablations`
- Error or symptom: COLMAP `global_mapper` logs `CUDSS_STATUS_ALLOC_FAILED` during global positioning, followed by `Ceres Solver Report ... Termination: FAILURE`, but the surrounding pipeline can still continue and write SfM outputs.
- Context or command: Full-dataset SfM ablation with `advanced.sfm.feature_extraction.max_num_features: 16384` and GPU global positioning enabled.
- Likely cause: The 16k feature setting creates a larger global-positioning problem than the cuDSS-backed GPU solver can factorise reliably on this setup. Because COLMAP can continue after the failed solve, a zero process exit is not enough to prove the reconstruction is usable.
- Fix or workaround: Treat runs with these log signatures as warning/failure cases during ablation analysis. Prefer the 4096/default feature-count variants unless a future COLMAP build or CPU/global-positioning configuration is deliberately tested and shown to avoid the failed solve.

## 2026-07-04 - COLMAP ALIKED Matcher Runtime Model Download

- Branch: `main`
- Error or symptom: ALIKED matching starts by downloading `bruteforce-matcher.onnx`, or fails on a network-restricted worker after ALIKED feature extraction succeeded.
- Context or command: COLMAP `sequential_matcher`, `vocab_tree_matcher`, or `matches_importer` with `--FeatureMatching.type ALIKED_BRUTEFORCE`.
- Likely cause: ALIKED extraction model paths are separate from the ALIKED brute-force matcher model path. Baking `aliked-n16rot.onnx` and `aliked-n32.onnx` is not enough.
- Fix or workaround: Pass `--AlikedMatching.bruteforce_model_path` explicitly. The Docker image should set `ALIKED_BRUTEFORCE_MATCHER_MODEL_PATH=/opt/colmap/models/aliked-bruteforce-matcher.onnx`, and the command builder should forward that path for all ALIKED matching passes.

## 2026-07-04 - `python -m reefs.cli` Exits Without Running

- Branch: `main`
- Error or symptom: `PYTHONPATH=src uv run python -m reefs.cli ...` exits with code 0 but does not create or update run outputs.
- Context or command: Local scratch proof runs invoking the Click CLI module directly.
- Likely cause: `src/reefs/cli.py` defines `app = run` but does not call the Click app from a `__main__` block, so `python -m reefs.cli` imports the module and exits.
- Fix or workaround: Invoke the app explicitly with `PYTHONPATH=src uv run python -c 'from reefs.cli import app; app()' ...`, or add a proper console-script/module entrypoint before relying on `python -m reefs.cli`.

## 2026-07-04 - LFS v0.5.2 Does Not Support Eval Disable Flag

- Branch: `main`
- Error or symptom: LFS eval fails immediately with `Parse error: Flag could not be matched: no-save-eval-images`.
- Context or command: `splat.eval` using `configs/test.yml`, which pointed at the older `lichtfeld-studio-v0.5.2` binary.
- Likely cause: The pipeline's eval command builder emits `--no-save-eval-images`, which is supported by the newer pinned `lichtfeld-studio-6d591a34` build used by recent smokes, but not by the older v0.5.2 binary.
- Fix or workaround: For eval runs, set `tools.lfs_bin` and `advanced.splat.train.lfs_config` to the pinned `lichtfeld-studio-6d591a34` build/config or rebuild/update the configured LFS binary. Docker image `cr.eu-north1.nebius.cloud/e00eqkjz0mkvvedmrd/3dreefs:1e696e2` already includes the matching eval config files.

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

## 2026-06-24 - Docker LFS Build And Runtime Library Paths

- Branch: `docker`
- Error or symptom: LichtFeld Studio Docker builds can fail on missing GTK/C++23/CUDA stub pieces, and runtime launches can fail on missing `libusd_usdGeom.so`, `libOpenMeshCore.so.11.0`, or `libcuda.so.1`.
- Context or command: Building the CUDA 12.8 Docker image and running `LichtFeld-Studio` inside `3dreefs:local`.
- Likely cause: LFS needs extra Linux GUI development headers even for headless builds, GCC/G++ 14 for `<print>`, a build-time CUDA stub `libcuda.so.1`, and runtime library paths for its copied build and vcpkg libraries. The real `libcuda.so.1` is supplied only when containers run with the NVIDIA runtime, such as `--gpus all`.
- Fix or workaround: Build LFS with GCC/G++ 14, install the GTK/Linux GUI dev dependencies, symlink the CUDA stub during Docker build, set `LD_LIBRARY_PATH` to the LFS build and vcpkg lib directories in the image, and run LFS containers with `--gpus all`.

## 2026-06-26 - Codex-Started Docker Jobs Receive External SIGTERM

- Branch: `docker`
- Error or symptom: Long Docker E2E jobs started from the Codex tool session stop abruptly. Docker events show `container kill ... signal=15`, then `signal=9`, with exit `137`; the pipeline run status may remain `running` because Python is terminated while waiting on COLMAP output.
- Context or command: Docker test dataset runs for `sfm,splat,splat.postprocess`, especially during COLMAP matching or LFS training.
- Likely cause: The Codex command execution supervisor cleans up long-lived attached/detached containers or systemd units it starts. Host Docker/GPU are not the failing parts.
- Fix or workaround: Start long Docker jobs from a normal user terminal, `tmux`, or the eventual cloud job runner, then monitor with `docker ps`, run logs, and `run_status.json`. Short chunks under the supervisor window can complete from Codex, but full E2E validation should be user-owned or cloud-runner-owned.

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

## 2026-06-18 - V3 Patch Selects Zero Cameras After Frustum Geometry Change

- Branch: `009-camera-selection-v3`
- Error or symptom: A patch with visible internal camera centres selects zero cameras, with `footprint_overlap_score` and `target_image_share` both zero.
- Context or command: `uv run main.py --config <config.yml> --steps splat.patch` after changing V3 footprint scoring.
- Likely cause: The frustum intersection was computed on the wrong projection plane, such as global `z=0`, so valid camera rays missed the patch target surface.
- Fix or workaround: Use the local fitted patch plane for frustum projection, then clip the result to the raw wildflow rectangle. Inspect a patch with `scratch/patch_frustum_diagnostics/make_v3_patch_frustum_viewer.py`.

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

## 2026-07-13 - ImageMagick Contact Sheet Exhausts Pixel Cache

- Branch: `main`
- Error or symptom: `montage` reports `cache resources exhausted` while building a contact sheet from several 8256 x 5504 JPEGs.
- Context or command: Dataset QC contact-sheet generation from many full-resolution camera images in one `montage` invocation.
- Likely cause: ImageMagick opens enough full-resolution inputs concurrently to exceed its default 1 GiB memory, 2 GiB map, or 2 GiB disk cache limit.
- Fix or workaround: Decode and resize each source image sequentially with `convert -auto-orient -thumbnail 640x424`, then run `montage` on the small temporary previews and remove them afterwards.

## 2026-07-14 - Host Post-Processing Does Not Reproduce The Nebius Runtime

- Branch: `main`
- Error or symptom: Local post-processing preflight reports COLMAP or LichtFeld Studio incompatibility even though the scientific Nebius run used the validated toolchain.
- Context or command: Running Dataset6 cleanup, merge, and SOG preparation from the host environment after downloading the accepted PLYs.
- Likely cause: The host environment is not the pinned Nebius container. This was a procedural deviation, not a change in the Dataset6 outputs or evidence that the datasets1-5 image was unstable.
- Fix or workaround: Do not run scientific or post-processing stages on the host. Use the normal wrapper and exact pinned image digest. If recovery is not supported by the wrapper, add and test a narrow resume mode rather than recreating container mounts, GPU exposure, `PYTHONPATH`, or preflight commands manually.

## 2026-07-25 - Downloaded Patch Outputs Cannot Enter Post-Processing

- Branch: `main`
- Error or symptom: `splat.postprocess` rejects a downloaded, manifest-verified
  patch set because the original COLMAP undistorted images and sparse model are
  absent.
- Context or command: Local cleanup, merge and SOG recovery from authoritative
  production PLYs and patch metadata.
- Likely cause: Splat preflight and pipeline source preparation ran
  unconditionally even when every requested stage consumed only trained patch
  artefacts.
- Fix or workaround: Postprocess-only requests now skip SfM source validation
  and sparse-source preparation. Patching, training and evaluation requests
  retain the strict source checks.

## 2026-07-25 - Large Merged SOG Fails WebP Lossless Encoding

- Branch: `main`
- Error or symptom: `splat-transform` reports `WebP lossless encode failed`
  while writing SOG position or spherical-harmonic label textures.
- Context or command: SOG export from a 68,743,748-Gaussian merged PLY;
  reproduced in v1.10.2 and v3.1.6.
- Likely cause: The WebP-backed SOG encoder cannot encode the generated
  high-pixel-count textures, despite sufficient system RAM and VRAM.
- Fix or workaround: Preserve the full merged PLY as authoritative. Generate a
  separate, explicitly named progressive-decimation PLY once, retain SH2, then
  export SOG from that reusable source and record both counts and checksums.
  A 58,143,458-Gaussian source still failed in v1.10.2 for Dataset 5, while a
  one-stage 45,000,000-Gaussian source encoded successfully; use 45 million as
  the proven conservative ceiling for this encoder path.

## 2026-07-14 - Nikon IPTC Metadata Can Abort COLMAP Undistortion

- Branch: `main`
- Error or symptom: COLMAP `image_undistorter` aborts with OpenImageIO `encode_iptc_iim_one_tag: data != nullptr` on the first Dataset7 Nikon JPEG/MPO image.
- Context or command: Dataset7 Stage 2 source generation in the pinned Nebius image; SfM had already completed successfully and only undistortion failed.
- Likely cause: OpenImageIO cannot serialise malformed copied IPTC metadata while writing undistorted images. The compressed image pixels are valid.
- Fix or workaround: Preserve the immutable input archive and completed sparse model. The SfM pipeline now recognises only this exact failure, creates an isolated ExifTool metadata-stripped working tree, requires matching per-image `ImageDataHash` inventories, deletes only the failed partial workspace and retries once. The same verified working tree is used for remaining 1024, 2048, and full-resolution undistortion passes; full resolution is not the fix.

## 2026-07-22 - Recover A Stage 2 Source Without Rerunning SfM

- Branch: `main`
- Error or symptom: A Stage 2 source VM is lost after its database and final refined sparse model were uploaded, but before all undistorted workspaces and source packaging were accepted.
- Context or command: Dataset7 metadata-safe recovery from the original failed source prefix.
- Likely cause: Undistortion or later packaging failed after the expensive SfM stages had completed.
- Fix or workaround: Use `scripts/nebius/launch_stage2_source_recovery_job.sh` with a new empty `RUN_ID` and the durable prefix in `RESUME_FROM_S3_URI`. The worker restores the source artefacts, invokes only `sfm.undistort`, and then runs the standard layout and source-bundle validation. Do not use the ordinary source launcher, which intentionally runs all SfM stages.
# 2026-07-22 - Colour profile or undistorted identity mismatch

- Branch: `012-colour-profiles-undistorted`
- Error or symptom: Profile application reports a dataset fingerprint, image mapping, or workspace membership mismatch.
- Context or command: `uv run main.py --config <config> --run-id <run> --steps splat`
- Likely cause: The profile belongs to another dataset, the reusable SfM source omitted its mapping manifest, or the undistorted tree is incomplete.
- Fix or workaround: Use the profile created from the same dataset and preserve `sfm/image_mapping.json` with the source bundle. Recreate the SfM source when strict legacy mapping reconstruction cannot verify every name.

## 2026-07-24 - Bash CSV Reader Retains CR In Final Field

- Branch: `feature/per-image-eval-extremes`
- Error or symptom: Downloaded files exist but ordinary glob/path lookups fail; `ls -b` shows `\r` at the end of every filename.
- Context or command: Reading a Python `csv` module manifest with `while IFS=, read ... target`; the manifest uses CRLF records.
- Likely cause: Bash removes the newline but retains the carriage return in the final CSV field.
- Fix or workaround: Parse CSV with Python or strip the final `\r` before using the field as a path. Rename affected files losslessly and rerun the complete checksum pass.

## 2026-07-23 - Completed Iterations Can Hide A Collapsed Splat Model

- Branch: `main`
- Error or symptom: LFS exits successfully at the requested iteration and the row is marked complete, but the final PLY contains far fewer splats than requested.
- Context or command: Dataset 6 full-resolution SIFT-global patch `p052` reached 30,000 iterations from a two-point sparse patch and produced only two splats.
- Likely cause: Completion classification checked process exit, iteration progress and output existence, but not the reported final splat count.
- Fix or workaround: Require the final reported splat count to equal `num_splats_per_patch`; otherwise record `splat_count_mismatch_expected_<N>_actual_<M|unknown>`. Keep the collapsed output as a failed diagnostic and select the next eligible patch.
