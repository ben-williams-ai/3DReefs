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
