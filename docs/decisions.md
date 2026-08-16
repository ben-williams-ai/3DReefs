# Decisions

## 2026-06-10 - Pipeline Foundation Shape

- Branch: `001-pipeline-foundation`
- Decision: Use one primary `uv run main.py --config <config>` entrypoint that derives normal paths from `project.dir` and writes run records under `<project.dir>/runs/<run_id>/`.
- Reason: Later SfM and splatting runs need reproducible configs, clear overrides, and auditable outputs before expensive work starts.
- Consequences: Public configs use placeholders. Local dataset paths belong in local config copies.

## 2026-06-10 - CLI Parser

- Branch: `001-pipeline-foundation`
- Decision: Use Click for the executable CLI parser.
- Reason: The required direct dotted override syntax, such as `--splat.train.num_iters 20000`, needs reliable unknown-option capture.
- Consequences: The CLI remains a thin wrapper around importable `src/reefs/` modules.

## 2026-06-10 - Foundation Does Not Run Heavy Stages

- Branch: `001-pipeline-foundation`
- Decision: Feature 1 validates and records the future pipeline surface but does not run COLMAP, undistortion, patching, LFS training, cleanup, compression, or merge stages.
- Reason: The foundation must be testable quickly and must establish config, logging, status, resume, and tool-validation behaviour first.
- Consequences: Later features can plug real stage execution into the existing run-record and preflight substrate.

## 2026-06-10 - Config Sections

- Branch: `001-pipeline-foundation`
- Decision: Public config files use `project` and `tools` as the only mandatory top-level sections; all other settings live under `advanced`.
- Reason: The user should make only the minimum required decisions up front, while advanced defaults remain visible and overrideable without cluttering the mandatory setup surface.
- Consequences: Dotted overrides for non-mandatory settings include the `advanced.` prefix, for example `--advanced.splat.train.num_iters 20000`.

## 2026-06-10 - COLMAP SfM Stage Integration

- Branch: `002-colmap-sfm-pipeline`
- Decision: Implement COLMAP SfM as an extension of the existing `main.py` run-record workflow rather than a separate runner.
- Reason: SfM must share config overrides, upfront resume/overwrite decisions, timing records, and logs with later pipeline stages.
- Consequences: `--steps sfm` is now an active COLMAP run, while `--steps sfm.preflight` provides a lightweight validation-only path.

## 2026-06-10 - Intrinsics Pre-Calculation Path

- Branch: `002-colmap-sfm-pipeline`
- Decision: Estimate intrinsics by running a selected-image COLMAP subset with intrinsics refinement enabled, then pass the estimated OPENCV camera parameters into full feature extraction and keep final reconstruction intrinsics refinement disabled by default.
- Reason: The spec requires default intrinsics pre-calculation, while the final large reconstruction should avoid silently changing intrinsics unless explicitly configured.
- Consequences: Default SfM runs include `sfm.intrinsics.*` stages before the full `sfm.extract` stage. The run manifest records the selected images and estimated camera parameters.

## 2026-06-10 - COLMAP 4.0.4 Command Validation

- Branch: `002-colmap-sfm-pipeline`
- Decision: Validate selected COLMAP subcommands with bounded help calls during SfM preflight.
- Reason: COLMAP command names and options can change across versions, and failures should happen before expensive feature extraction or matching.
- Consequences: Missing `global_mapper`, matcher commands, `model_converter`, `image_undistorter`, or enabled dense/mesh commands fail early.

## 2026-06-11 - Environment Variables For Local Tool Paths

- Branch: `002-colmap-sfm-pipeline`
- Decision: Public configs use environment-variable placeholders for COLMAP, LichtFeld Studio, `splat-transform`, and vocabulary-tree paths, with `.env.example` documenting the expected variables.
- Reason: Tool/resource paths are machine-specific and should not be copied into public configs.
- Consequences: Local users should copy `.env.example` to `.env` or export the variables before running public configs. The real `.env` remains gitignored.

## 2026-06-11 - Durable Stage-Level Run Records

- Branch: `004-run-resume-hardening`
- Decision: Create canonical run records as soon as a run directory is selected and update status/timings after each stage, rather than writing records only at the end.
- Reason: Long COLMAP and future LFS jobs can be interrupted by shells, tunnels, or host processes. End-only records make expensive runs hard to audit or resume.
- Consequences: Resumed runs can use `--run-id` to update the existing run directory in place. Missing or stale records are supplemented by filesystem inspection of generated SfM outputs.

## 2026-06-11 - Splat Patch Source Handling

- Branch: `003-splat-patching-training`
- Decision: Feature 3 consumes Feature 2 undistorted SfM outputs from the same run directory and exports a text sparse copy under `splat/source_sparse_txt/` when COLMAP undistortion produced binary sparse files only.
- Reason: Patch planning and diagnostics need inspectable image names, camera centres, and sparse point visibility, while COLMAP's undistorter commonly writes binary sparse models.
- Consequences: `splat.patch` should normally be run with `--run-id <sfm_run_id>` unless it is part of a future end-to-end command that has just produced SfM outputs in the active run.

## 2026-06-11 - Serial LFS Training

- Branch: `003-splat-patching-training`
- Decision: `splat.train` runs exactly one LFS process at a time and records status per patch.
- Reason: Large reef patches should use as much GPU memory as possible for quality; users who want unrelated jobs in parallel can launch separate commands themselves.
- Consequences: Patch training is slower but simpler to audit, and resume/overwrite decisions are resolved before any LFS process starts.

## 2026-06-15 - Old-Style View-Based Patch Camera Selection

- Branch: `005-splat-post-processing`
- Decision: Use one patching approach only: `wildflow.splat.patches` for birds-eye patch bounds, followed by the old proven `select_by_views` camera selector rebuilt cleanly in the new codebase.
- Reason: The old selector explicitly optimised boundary-visible points, projected image coverage, median depth, and balanced viewing sectors, which is important for sharp patch borders and avoids over-selecting near-duplicate local views.
- Consequences: The simplified visibility-plus-local-bonus selector is removed. Patch diagnostics now mirror the old useful artefacts and include a run-level patch summary.

## 2026-06-16 - Superseded Camera Selection Experiment

- Branch: `006-hybrid-camera-selection`
- Decision: This selector experiment is superseded and must not be used as the
  implementation source of truth.
- Reason: Later reef diagnostics showed that useful internal cameras could still
  be displaced by less useful neighbouring support cameras.
- Consequences: Future camera-selection work should start from the current
  feature branch and its fresh Spec Kit docs, not this historical experiment.

## 2026-06-17 - Superseded Camera Selection V2 Experiment

- Branch: `008-camera-selection-v2`
- Decision: This selector experiment is superseded and must not be used as the
  implementation source of truth.
- Reason: Visual inspection of reef patch diagnostics still showed useful
  internal cameras being dropped for neighbouring support cameras.
- Consequences: Existing V2 trial outputs are for comparison only and should not
  be treated as the preferred patching output.

## 2026-06-18 - Camera Selection V3 Internal-First Selector

- Branch: `009-camera-selection-v3`
- Decision: Use one production patch camera selector: keep useful internal
  cameras first, then add only capped one-ring neighbouring external support.
- Reason: Reef diagnostics showed useful internal cameras being displaced by
  support views. V3 makes internal coverage the invariant and reserves external
  support as optional capped context.
- Consequences: Patch bounds are generated with the internal camera target.
  Selector diagnostics keep the existing filenames but now report V3 internal
  and external camera categories.

## 2026-06-18 - Camera Selection V3 Fitted Projection Plane

- Branch: `009-camera-selection-v3`
- Decision: Use the raw wildflow patch rectangle as the footprint, but project
  camera frusta onto a local fitted sparse-point plane before clipping them to
  that rectangle.
- Reason: A global `z=0` plane missed valid cameras, while a horizontal
  median-height plane could visibly diverge from sloped local reconstruction
  surfaces.
- Consequences: Sparse points provide track evidence and the projection plane
  only. They do not define the footprint polygon, target polygon, sparse hull,
  or sparse-density area.

## 2026-06-11 - Dataset 1 Large Splat Training Baseline

- Branch: `003-splat-patching-training`
- Decision: Use `tmux` for long dataset runs and keep `advanced.splat.patching.max_cameras: 800` as the current Dataset 1 large-run baseline on the RTX 6000 Ada.
- Reason: Dataset 1 completed 11 serial LFS patch trainings at 30,000 iterations and 1,500,000 splats per patch without OOM.
- Consequences: Dataset 2 can start from the same patch-size default, but memory and logs should be monitored. If OOM occurs, reduce the patch size to 500, then 200 if needed.

## 2026-06-12 - Dataset 2 Full Pipeline Baseline

- Branch: `003-splat-patching-training`
- Decision: Dataset 2 can use the same default large-run settings as Dataset 1: `advanced.splat.patching.max_cameras: 800`, 30,000 LFS iterations, and 1,500,000 splats per patch.
- Reason: The full current pipeline completed from SfM through serial LFS patch training on 6,590 images, producing 9 complete patch splats without OOM or warnings.
- Consequences: Patch size 800 remains a reasonable starting point for similar reef datasets on the RTX 6000 Ada. The final Dataset 2 patch was slower than the others, so per-patch timing should still be reviewed before assuming uniform training time.

## 2026-06-15 - Wildflow Post-Processing Backend

- Branch: `005-splat-post-processing`
- Decision: Require wildflow for patch cleanup and cleaned PLY merge, and keep `splat-transform` only for final SOG export.
- Reason: The old successful cleanup path used `wildflow.splat.cleanup_splats`, and the old PLY merge path used `wildflow.splat.merge_ply_files`. Wildflow is available as a public Python package, so keeping a weaker fallback would add maintenance overhead and reduce cleanup quality.
- Consequences: Cleanup settings from the old coral config remain recorded in manifests and configs. Runs fail during preflight if wildflow cleanup/merge functionality is unavailable.

## 2026-06-15 - Final SOG Lives With Merged PLY

- Branch: `005-splat-post-processing`
- Decision: Store the final site SOG beside the merged cleaned PLY under `splat/merged/`.
- Reason: The SOG is a compressed representation of the merged site-level PLY, so keeping both primary site outputs together is easier to inspect and avoids a redundant output folder.
- Consequences: New runs write `splat/merged/merged_splat.ply` and `splat/merged/merged_splat.sog`. Existing runs with `splat/sog/merged_splat.sog` should move or regenerate the SOG if they need the new layout.

## 2026-06-22 - Optional Colour Restoration Workflow

- Branch: `010-image-recolour-workflow`
- Decision: Add colour restoration as a resumable run-scoped workflow under `src/reefs/colour/`, with state at `<project.dir>/runs/<run_id>/colour_restoration/state.json` and corrected outputs at `<project.dir>/recoloured_images/`.
- Reason: Colour edits need their own ordering, keyframe interpolation, Wildflow-style filter stack, GUI state, standalone commands, and downstream gates while preserving raw-image SfM geometry.
- Consequences: Raw images remain read-only and drive SfM feature extraction, matching, reconstruction, and COLMAP undistortion. Completed colour outputs are used only for splatting-stage image inputs and review. Existing corrected outputs require explicit overwrite confirmation, and splatting waits whenever required colour state is active, applying, incomplete, or failed.

## 2026-07-22 - Apply Colour Profiles After Undistortion

- Branch: `012-colour-profiles-undistorted`
- Decision: Save dataset-specific GUI profiles and apply them only to run-local copies of consumed undistorted training/evaluation workspaces; add explicit unattended `profile` mode.
- Reason: Raw corrected pixels do not match undistorted camera geometry, and project-level filenames can diverge after COLMAP-safe staging.
- Consequences: SfM persists exact image identity mapping, splat inputs always match their sparse workspace, off mode remains unchanged, and legacy `recoloured_images/` are review-only.

## 2026-08-16 - Cross-Dataset Production Defaults

- Branch: `agent/organise-experiment-results`
- Decision: Set the example and production dataset configs to 1024-pixel SIFT
  feature extraction with the global mapper, then 2048-pixel training with at
  most 200 cameras and 2 million Gaussians per patch.
- Reason: These settings produced the best mean LPIPS across the completed
  Stage 1 and Stage 2 ablations, rather than being selected for one dataset.
- Consequences: SfM and training resolution remain separate settings. Formal
  experiment grids retain every comparison value; test configs retain their
  deliberately small settings.
