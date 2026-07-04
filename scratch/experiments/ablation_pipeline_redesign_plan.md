# Ablation Pipeline Redesign Plan

Date: 2026-07-03

This is a scratch planning document for adding pipeline-supported resolution sweeps, ALIKED/SIFT feature sweeps, improved held-out splat evaluation, LPIPS reporting, and cloud-safe ablation orchestration.

This is not an official experiment result. It is intended to be reviewed before implementation.

## Current Answer Snapshot

### Downsampling Through COLMAP

- Yes, `advanced.sfm.feature_extraction.max_image_size` is the right primary knob for making COLMAP feature extraction operate at a bounded image size.
- In the current code, that setting is already passed to `feature_extractor` in the shared command builder.
- Because the same command builder is used by both intrinsics pre-calculation and the main SfM extraction, the setting already affects both paths.
- What is missing is the default coupling into undistortion. `image_undistorter` currently uses only `advanced.sfm.undistortion.max_image_size`, which defaults to `4096`.
- Desired behaviour: if `advanced.sfm.feature_extraction.max_image_size` is set, undistortion should default to the same value unless the user explicitly overrides `advanced.sfm.undistortion.max_image_size`.
- If `advanced.sfm.feature_extraction.max_image_size` is `null` or absent, undistortion should keep the current `4096` default unless explicitly configured otherwise.
- LFS should not need a separate image-size change for this experiment mode, because LFS trains on the already-undistorted patch images.

### Eval Against Undistorted Training Images

- Updated decision: formal eval should use the same undistorted patch images that LFS trains on.
- Do not evaluate splats against raw distorted images. LFS renders in the undistorted COLMAP camera/image space, so raw distorted targets are the wrong comparison target.
- For a full feature-extraction variant, undistortion falls back to `4096`; LFS trains and evaluates against those `4096` undistorted patch images.
- For `2048` and `1024` variants, undistortion follows the feature size; LFS trains and evaluates against the corresponding `2048` or `1024` undistorted patch images.
- This means lower-resolution variants are evaluated at their own training resolution. That is a deliberate experiment choice for now and must be recorded clearly as `eval_target_source: training_undistorted` or equivalent.

### LPIPS

- This may be smaller than first feared, but still needs testing.
- The installed LFS source has an LPIPS field in benchmark scripts and events, but the inspected training metrics code says LPIPS is currently `0.0f` in that code path.
- Existing `metrics.csv` files in this repo mostly have the header `iteration,psnr,ssim,time_per_image,num_gaussians`, with no `lpips`.
- The repo parser currently keeps only `psnr`, `ssim`, `time_per_image`, and `num_gaussians`.
- Implementation must first confirm whether the built LFS binary can produce real LPIPS. If not, LPIPS either requires an LFS-side implementation or a separate Python renderer/evaluator.
- If LPIPS requires a new Python dependency only, that means `uv.lock`, tests, Docker rebuild, and Nebius smoke validation. If it requires LFS code, it is a larger cross-project change (note we are not editing the lfs source code in this project, we write and edit all our own).

### Holdout Selection

- The current ablation code picks held-out images itself, not LFS.
- It uses `src/reefs/experiments/ablations/holdout.py`.
- New holdouts are selected from registered internal patch cameras, ordered along the patch's dominant spatial axis, then adjusted so the count can be represented by LFS `--test-every`.
- Current default holdout fraction is `0.10` in `experiments/ablations/ablation_config.yml`.
- The prompt's desired default is `0.15`. UPDATE: keep this at 0.10, I am ovberiding what i said! consder this stance he latest stance.
- Current canonical holdouts are scoped by dataset, job id, patch size, and patch id. They are not shared across variants.
- Stage 2 needs more stable canonical scoping because patch IDs and patch contents should be comparable across repeated splat variants when the SfM source is shared.

### ALIKED

- COLMAP 4.0.4 in this environment exposes `--FeatureExtraction.type` and `--AlikedExtraction.*` options.
- This is probably not an external hloc-style import job; it can likely be added as a moderate COLMAP command/config extension.
- It still needs a spike because the ONNX model download/cache path, Docker offline behaviour, feature counts, GPU support, and matcher compatibility must be verified locally and on Nebius.
- Recommended first ALIKED variant: `FeatureExtraction.type=ALIKED` with `AlikedExtraction.max_num_features` exposed and defaulted explicitly.

### Incremental Vs Global Mapper

- The current pipeline already has `advanced.sfm.reconstruction.backend` with `global` and `incremental`.
- Sweeping this is mostly config/grid work.
- Runtime risk is real. Incremental mapper may be slower on large datasets and can behave differently with multi-camera intrinsics and high match counts.
- Estimate it only after a local smoke and one Nebius small dataset job; do not commit to launching all incremental jobs blind. NOTE: do not run a local incremental job on full test data, that will take too long. do it on nebius if useful.

### Jobs And Parallelism

- A job should mean one dataset plus one variant, including SfM, patching, and serial training/eval for the selected validation patches.
- It should not mean one VM per patch.
- Stage 1 sweep as requested is 3 image sizes x 2 feature types x 2 mappers = 12 variants per dataset.
- For datasets 1-4, Stage 1 is 48 jobs.
- Stage 2, if using patch sizes `[200, 400, 800]` and splat counts `[1000000, 2000000, 3000000]`, is 9 jobs per dataset, so 36 jobs for datasets 1-4.
- Total broad sweep is therefore 84 cloud jobs before any optional final selected reruns.
- Current public IPv4 quota has previously limited fanout to 3 public-IP VMs, even if H100 quota is higher. Do not assume 29 H100 quota means 29 simultaneous public-IP workers unless public-IP quota or worker networking has changed.

### Cost Sketch

Nebius official pricing on 2026-07-03 lists NVIDIA H100 NVLink at `$3.85` per GPU-hour on-demand and `$2.15` per GPU-hour preemptible from 2026-06-01. Billing for running VM compute is per second with one-hour pricing units, and stopped VM compute is not charged, although disks still are. Source checked: https://docs.nebius.com/compute/resources/pricing and https://nebius.com/prices. NOTE: we want on-dmand jobs, ont preemptible.

Use this as a planning range, not a quote:

- Stage 1 broad sweep: 48 jobs.
- If a full job averages 6-12 H100 hours, Stage 1 is about 288-576 H100-hours, or about `$1.1k-$2.2k` on-demand before storage/VAT.
- Stage 2 broad sweep: 36 jobs.
- If a Stage 2 job reuses SfM and averages 3-7 H100 hours for patching plus 10 serial eval splats, Stage 2 is about 108-252 H100-hours, or about `$416-$970` on-demand before storage/VAT.
- Broad total: roughly `$1.5k-$3.2k` on-demand, with large uncertainty.
- This should be tightened by running one 500-iter smoke, one 15k eval smoke, and one full 30k-ish validation job on Nebius before launching the whole grid.

## Code Reality Checked

Key current integration points:

- Main CLI writes `effective_config.yml`, `run_manifest.json`, `cli_overrides.json`, `run_status.json`, and `timings.json`.
- Main SfM path is in `src/reefs/sfm/pipeline.py`.
- COLMAP command building is in `src/reefs/colmap/commands.py`.
- Config schema is in `src/reefs/config/models.py`.
- Main LFS training path is in `src/reefs/splat/pipeline.py` and `src/reefs/lfs/runner.py`.
- Current ablation runner is in `src/reefs/experiments/ablations/runner.py`.
- Current ablation eval path is in `src/reefs/experiments/ablations/splat_eval.py`.
- Current holdout logic is in `src/reefs/experiments/ablations/holdout.py`.
- Current ablation ledgers are in `src/reefs/experiments/ablations/ledger.py`.
- Nebius worker/launcher are `scripts/nebius/run_ablation_worker.sh` and `scripts/nebius/launch_worker_vm.sh`.
- Existing Nebius pitfalls are recorded in `scratch/experiments/troubleshooting_nebius.md`.

Important drift to fix:

- Main pipeline can run `sfm,splat,splat.postprocess`, but ablation eval directly builds LFS commands instead of using a first-class main-pipeline eval mode.
- Shell worker has extra scratch eval behaviour that is not the same abstraction as the Python ablation runner.
- Current ablation ledgers do not have `lpips`, per-eval-iteration metric rows, feature type, image size, or mapper columns.
- Current patch selection is per job, which is acceptable for Stage 1 but not sufficient for Stage 2 comparability.

## Design Principles

- Keep official pipeline code and ablation code close: ablations should run variants of the main pipeline config with eval enabled.
- Keep experiment-specific launch scripts, temporary configs, result mirrors, and analysis scripts under `scratch/`.
- Put reusable capability in the main package only when the main pipeline or formal ablation runner needs it.
- Make every run traceable from result row to source config, effective config, code commit, Docker image, dataset manifest, command line, and logs.
- Never overwrite scientific results without keeping an immutable previous row or backup.
- Use short local tests first, then short Nebius smokes. A full enbius run on a big job is final alst thing to do when we think the sweep is liekly ready to go, this takes ages so stay away from this until absoutely sure it may be ready. always use the watch-job skill to monitor jobs.
- Do not add colour-correction assumptions to the sweep, but keep colour restoration compatible with the main pipeline.

## Target Experiment Semantics

### Image Categories

Use these names consistently:

- Raw images: original camera images from the dataset. They may contain lens distortion and should not be used directly as LFS metric targets.
- Feature-extraction images: raw images as read by COLMAP feature extraction, optionally bounded by `advanced.sfm.feature_extraction.max_image_size`. COLMAP handles this internally; these are not a separate metric target.
- Undistorted SfM images: images written by COLMAP `image_undistorter` from the selected sparse model. Their size is controlled by the effective undistortion size.
- Patch training images: the subset/copy of undistorted SfM images selected for each LFS patch. These are the images LFS trains on.
- Eval target images: held-out images from the same patch training image set, with the same undistorted camera model and same resolution as the patch training images.

Current eval decision: use held-out patch training images as the metric target. Do not use raw distorted images, and do not require a separate full-resolution undistorted target tree for formal ablations.

### Stage 1

Purpose: compare SfM variants using the same downstream eval protocol.

Sweep dimensions:

- Image size: `null` full-res feature extraction with `4096` undistortion, `2048`, `1024`.
- Feature type: `SIFT`, `ALIKED`.
- Mapper backend: `global`, `incremental`.

Fixed settings:

- Use current AIMS-style defaults unless the sweep dimension changes them (see the current example config for aims style settings).
- Matching should remain AIMS-style: sequential matching with loop detection where intended, not accidental full vocab-tree matching unless the config explicitly says so.
- Cross-camera pair generation/matching should follow the chosen AIMS setting, with the matching pass state recorded explicitly.
- Patch cap default: 400 cameras.
- Splat cap default: 2,000,000 unless changed by Stage 2.
- Validation patches: up to 10 per dataset/job, fewer if fewer exist.
- Holdout fraction: 10%.
- Eval iterations: at least every 5,000 iterations for longer eval runs.
- Eval target: held-out images from each patch's own undistorted training image set, at that variant's effective undistortion size.

### Stage 2

Purpose: use the best Stage 1 SfM outcome and sweep splat design settings.

Sweep dimensions:

- Patch camera cap: suggested `[200, 400, 800]`.
- Splat cap: suggested `[500000, 1000000, 2000000]`.

Fixed settings:

- SfM source comes from the selected Stage 1 winner per dataset or a single overall winner, depending on review decision.
- Same selected validation patches and holdouts should be reused across Stage 2 variants where the same SfM source and patch ID exist.
- Eval metrics: PSNR, SSIM, LPIPS if LPIPS is genuinely implemented; otherwise PSNR and SSIM with LPIPS blank/excluded from ranking.
- Eval target: held-out images from the same undistorted patch image set used for training.
- Cleanup, merge, and SOG are optional for sweeps; keep them runnable for selected final visual inspection.

## Work Packages

### WP0 - Freeze The Intended AIMS Baseline

- [x] Define one named AIMS baseline block in the ablation config or generator.
- [x] Include all key settings explicitly, not by relying on defaults.
- [x] Record matching mode, loop detection, vocab-tree matcher use, guided matching, cross-camera pair generation, cross-camera matching pass, sparse refinement, intrinsics refinement, feature type, feature image size, mapper backend, undistortion size, patch cap, splat cap, and LFS max width.
- [x] Add a small config-diff report per variant that highlights only sweep changes from the baseline.
- [x] Add a pre-run assertion that a Stage 1 variant changes exactly the intended dimensions.
- [x] Add tests that the generated `sfm_full_sift_global`, `sfm_2048_sift_global`, `sfm_1024_aliked_incremental`, etc. produce expected overrides.

Acceptance:

- [x] A reviewer can inspect one generated manifest and see every important SfM/splat setting.
- [x] The mistake class "silent default drift changed the experiment" is guarded by tests and manifest checks.

### WP1 - Pipeline-Supported Image Size Semantics

- [x] Keep `advanced.sfm.feature_extraction.max_image_size: int | null` as the primary SfM image-size knob.
- [x] Add an explicit undistortion resolution policy, for example `advanced.sfm.undistortion.max_image_size: int | null` plus `advanced.sfm.undistortion.follow_feature_extraction_max_image_size: true`.
- [x] Implement effective undistortion size resolution:
  - if undistortion size is explicitly set, use it;
  - else if feature extraction max image size is set, use that;
  - else use `4096`.
- [x] Preserve raw image roots and camera folder structure.
- [x] Record the effective feature extraction size and effective undistortion size in `run_manifest.json`.
- [x] Add tests for COLMAP command builders and pipeline manifest output.
- [x] Add an integration-style fake-COLMAP test proving intrinsics extraction, main extraction, and undistortion all see the intended sizes.

Acceptance:

- [x] `null` feature size produces no `--FeatureExtraction.max_image_size` and undistort uses `4096`.
- [x] `2048` feature size produces `--FeatureExtraction.max_image_size 2048` for intrinsics and main extraction and `image_undistorter --max_image_size 2048`.
- [x] Explicit undistortion override still wins when deliberately set.

### WP2 - Feature-Type Support: SIFT And ALIKED

- [x] Extend config schema with `advanced.sfm.feature_extraction.type`, likely literal `SIFT` or `ALIKED`.
- [x] Add ALIKED config fields:
  - `max_num_features`;
  - `min_score`;
  - optional model path selector or model paths for n16rot/n32.
- [x] Update `build_feature_extractor()` to emit `--FeatureExtraction.type`.
- [x] Emit SIFT options only for SIFT and ALIKED options only for ALIKED, unless COLMAP accepts harmless unused options after testing.
- [x] Decide model policy for Docker/Nebius:
  - bake ONNX models into the image; or
  - download/cache on first run; or
  - mount/upload as Object Storage assets.
- [x] Prefer baking or pre-staging models to avoid cloud runs failing on outbound network/model-cache surprises.
- [x] Download and stage ALIKED vocab trees next to the existing Nebius SIFT vocab tree asset:
  - `vocab_tree_faiss_flickr100K_words64K_aliked_n16rot.bin`;
  - `vocab_tree_faiss_flickr100K_words64K_aliked_n32.bin`.
- [x] Extend Nebius launcher/worker asset staging so ALIKED variants mount/pass `ALIKED_N16ROT_VOCAB_TREE_PATH` and `ALIKED_N32_VOCAB_TREE_PATH`, not only `VOCAB_TREE_PATH`.
- [x] Add unit tests for SIFT and ALIKED command construction.
- [x] Add a 20-image local ALIKED SfM smoke before any cloud run.

Acceptance:

- [x] ALIKED feature extraction completes locally on `configs/test.yml` or a scratch derivative.
- [x] Nebius preflight proves the pushed image has COLMAP/LFS and mounted SIFT + ALIKED vocab assets without relying on an unrecorded model download. NOTE: the first ALIKED cloud smoke exposed a separate `bruteforce-matcher.onnx` runtime download; the rerun with image `61ada12` and Git ref `491bf3d` passed with explicit local matcher model paths and no COLMAP download log lines.
- [x] Feature count and keypoint tables are recorded for SIFT vs ALIKED.

### WP3 - Mapper Backend Sweep

- [x] Keep using `advanced.sfm.reconstruction.backend`.
- [x] Ensure global mapper and incremental mapper options are independently configurable.
- [x] Add tests that each backend emits the correct COLMAP subcommand and BA flags.
- [x] Add per-backend warning thresholds to catch multiple sparse models, low registration, graph fragmentation, or zero reprojection errors.
- [x] Run one small local incremental smoke before enabling the full grid.
- [x] Run one Nebius incremental smoke on `test_dataset` or one small dataset patch source.

Acceptance:

- [x] Both backends can run through SfM and patch generation.
- [x] Runtime and registration metrics are comparable in the same ledger schema.

### WP4 - First-Class Eval Mode In Main Pipeline

- [x] Add an eval config block in main config, e.g. `advanced.eval.enabled`.
- [x] Keep the default off for normal pipeline runs.
- [x] Move reusable holdout/eval dataset construction out of ablation-only modules into a main package module, or make ablation modules call a main pipeline eval API.
- [x] Ensure ablation jobs call main pipeline eval behaviour rather than duplicating LFS command construction.
- [x] Support running `sfm,splat.patch,splat.eval` without cleanup/merge/SOG.
- [x] Keep `splat.train` normal mode unchanged for non-eval runs.
- [x] Make eval output paths deterministic and per-attempt, not overwritten.

Acceptance:

- [x] One local command can run a normal non-eval pipeline exactly as before.
- [x] One local command can run eval mode and produce holdout manifests, LFS metrics, eval dataset manifest, and result rows.
- [x] Ablation runner uses the same eval function as the main pipeline.

### WP5 - Undistorted Held-Out Evaluation Design

This is the most important scientific design point.

- [x] Define the image categories used by the experiment: raw images, COLMAP feature-extraction inputs, undistorted SfM images, patch training images, and eval target images.
- [x] Decide not to evaluate against raw distorted images.
- [x] Decide not to use a separate larger full-resolution undistorted target tree for formal ablation metrics.
- [x] Use held-out images from each patch's own undistorted training image set as the formal eval target.
- [x] **NEW** Rename or normalise eval target labels so formal runs clearly report `training_undistorted` or `patch_undistorted` rather than ambiguous `resized_undistorted` or `full_resolution_undistorted`.
- [x] **NEW** Remove or disable formal-ablation use of the separate `full_resolution_undistorted_images_dir` path unless it is explicitly requested for a future diagnostic experiment.

Acceptance:

- [x] Eval manifests state image source, dimensions, camera source, resize/crop policy, and metric implementation.
- [x] Downsampled SfM/training variants are evaluated against held-out images at their own effective undistortion/training size.
- [x] The report table makes it impossible to confuse raw image size, feature-extraction size, undistortion/training size, and eval target size.
- [x] **NEW** A `1024` or `2048` variant reports final metrics against held-out `1024` or `2048` undistorted patch images respectively, not raw distorted images and not a separate larger target tree.

### WP6 - 5k Evaluation And Save Cadence

- [x] Expose LFS eval/save steps in config, e.g. `advanced.splat.eval.steps: [5000, 10000, 15000]`.
- [x] Generate an LFS config JSON when needed so `eval_steps` and `save_steps` are explicit.
- [x] Confirm LFS writes checkpoints at `save_steps`; current LFS source indicates it does.
- [x] Confirm whether it writes PLYs at every save step or a file that can be used in the eval. Current source suggests regular `save_steps` save checkpoints, while final output is the stable PLY; PLY per step needs testing.
- [x] If only checkpoints are written, choose one:
  - evaluate from checkpoints if the evaluator supports checkpoint loading; or
  - add/export PLY from checkpoints after training; or
  - add a small LFS-side PLY export hook at save steps.
- [x] Store per-iteration metrics in a long-form table, not only final metrics.
- [x] Keep final summary columns for the latest/final iteration.

Acceptance:

- [x] A 15k run produces eval rows for 5k, 10k, and 15k.
- [x] Result ledgers include both per-iteration metrics and a final rollup.

### WP7 - LPIPS Metrics

- [x] First inspect the built LFS binary output on an eval run to see whether `metrics.csv` contains real LPIPS.
- [x] If LFS provides real LPIPS:
  - [x] update parser to accept both old and new headers;
  - [x] add `lpips` to result ledgers and reports;
  - [x] add tests using old `iteration,psnr,ssim,time_per_image,num_gaussians` and new `iteration,psnr,ssim,lpips,time_per_image,num_gaussians`.
- [x] If LFS does not provide real LPIPS:
  - implement LPIPS in a separate Python metric module only after the formal undistorted held-out eval source is settled;
  - add dependency deliberately, probably `lpips` or a vetted Torch implementation;
  - update `pyproject.toml` and `uv.lock`;
  - add Docker rebuild and Nebius smoke tests.
- [x] Ensure lower-is-better handling is correct in ranking.
- [x] **NEW** Implement real LPIPS before using LPIPS in final ranking. The current LFS build does not write a `lpips` metric, and its event-side `0.0f` placeholder must not be consumed.
- [x] **NEW** When LPIPS is added, compute it on the same held-out undistorted patch images as PSNR/SSIM.
- [x] **NEW** Add a tiny LPIPS benchmark on `test_dataset` to record runtime/storage impact before rebuilding Docker or launching Nebius validation.
BEN NOTE FOR CODEX: Now note does this mean we must do eval seperately with lpips? so psnr and ssim could still run during the lfs steps. but if LFS doesnt support LPIPS then we will have to a seperate eval job, making sure we use the exact same images - if this is needed it could run at the end so as not to compete for GPU space if that is best but will need to be able o find the plys or whatever the relevant file is needed.

Acceptance:

- [x] Reports include PSNR, SSIM, and LPIPS.
- [x] Missing LPIPS is represented as missing/failed, not `0.0`, unless it is a real metric value.
- [x] **NEW** At least one real run has a non-placeholder LPIPS value in `metrics.csv`, `metrics_long.csv`, and final reports, or formal ranking explicitly excludes LPIPS until that is true.

### WP8 - Holdout And Patch Selection

- [x] keep default holdout fraction to `0.10`.
- [x] Keep deterministic spatially spaced selection for new holdouts.
- [x] Add a canonical holdout identity that can be reused across variants where patch image sets match.
- [x] For Stage 1, allow patch IDs to differ by variant because SfM outputs may create different patch layouts.
- [x] For Stage 2, reuse the same SfM source and patch layout, so patch IDs and holdout images should be identical across patch-size/splat-count variants where possible.
- [x] Write holdout manifests before training starts and treat them as immutable inputs.
- [x] If a requested holdout image is missing from a variant, fail or mark the row invalid rather than silently selecting a different holdout for a comparable run.

Acceptance:

- [x] Stage 1 summary says patch/holdout selection is per SfM job.
- [x] Stage 2 summary says patch/holdout selection is shared for comparable splat variants.
- [x] Tests cover reuse, missing holdout images, and 10% expressible-count adjustment.

### WP9 - Ablation Grid And Runner

- [x] Replace or archive outdated scratch docs:
  - `scratch/experiments/nebius_remaining_jobs_runbook.md`;
  - `scratch/experiments/experiment_job_matrix.md`.
- [x] Generate a new Stage 1 manifest from the requested grid.
- [x] Generate a new Stage 2 manifest after Stage 1 winner selection.
- [x] Ensure each job maps to one dataset plus one variant plus all selected eval patches serially.
- [x] Make `manifest.csv` append/merge safe and do not drop unknown existing rows without archiving.
- [x] Add status states:
  - planned;
  - running;
  - complete;
  - complete_with_warnings;
  - failed;
  - superseded;
  - archived.
- [x] Store per-job `effective_config.yml` or equivalent generated config before launch.
- [x] Store exact command lines and environment summary.
- [x] Add a dry-run command that prints job count, estimated hours, estimated cost, and planned output roots.

Acceptance:

- [x] `ablation_experiment.py manifest` creates a reviewable plan with 48 Stage 1 jobs.
- [x] No cloud job launches without a materialised config and manifest row.

### WP10 - Nebius Worker Convergence

- [x] Keep VM launcher secrets handling from current scripts.
- [x] Keep direct raw image mount at `/scratch/3dreefs/project/raw_images`.
- [x] Keep real FAISS vocab tree staging; never use an empty placeholder when loop detection is on.
- [x] Keep `--project-dir /scratch/3dreefs/project`.
- [x] Keep explicit `GIT_REF` and Docker `IMAGE_NAME` in every run record.
- [x] Ensure worker mode runs the same Python ablation entrypoint used locally.
- [x] Remove or wrap bespoke shell-side eval summaries once the Python runner owns eval output.
- [x] Add a cloud-side "preflight only" mode if useful:
  - verify dataset tarball;
  - verify vocab tree;
  - verify Docker image;
  - verify COLMAP/LFS/splat-transform versions;
  - upload a preflight result and exit.
- [x] Ensure VM deletion happens only after outputs and exit marker upload attempts.

Acceptance:

- [x] Local and Nebius use the same ablation config schema and same runner semantics.
- [x] Nebius outputs include exit marker, logs, run records, ledgers, resource samples, and effective config.

### WP11 - Record Keeping And Immutable Results

- [x] Treat each formal run root as immutable once a job starts.
- [x] Use timestamped or content-hashed attempt directories for repeated attempts.
- [x] Never rewrite a completed row without creating a backup or a superseding row.
- [x] Keep append-only `events.jsonl` per job for state transitions.
- [x] Keep atomic CSV writes for summary ledgers, but also keep JSONL event history.
- [x] Add a `run_identity.json` per job:
  - run id;
  - dataset name;
  - dataset manifest/checksum;
  - source config path;
  - effective config hash;
  - git commit;
  - dirty git status flag;
  - Docker image digest/tag;
  - Nebius instance type and region;
  - command line;
  - created_at.
- [x] Add `metrics_long.csv` for per-iteration, per-patch metric rows.
- [x] Add `metrics_final.csv` or keep `results_splat.csv` as final rollup.
- [x] Add `warnings.jsonl` for known warning classifiers.
- [x] Add a small reader script under `scratch/` first, then promote only if it proves useful.
- [x] **NEW** Add the selected sparse model id/path to completed run manifests and SfM result ledgers so multi-model COLMAP outputs can be traced without reopening logs.

Acceptance:

- [x] A result row can be traced back to the exact command, effective config, code, image, dataset, patch metadata, holdout manifest, and log files.
- [x] Re-running a job cannot silently overwrite the original result.
- [x] **NEW** A completed SfM row records which sparse model was selected when COLMAP produced one or more sparse model directories.

## Proposed Config Shape

Example shape to refine during implementation:

```yaml
advanced:
  sfm:
    feature_extraction:
      type: SIFT
      max_image_size: null
      max_num_features: 8192
      sift:
        estimate_affine_shape: true
        domain_size_pooling: true
      aliked:
        model: n32
        max_num_features: 8192
        min_score: 0.2
        n16rot_model_path: null
        n32_model_path: null
    undistortion:
      max_image_size: null
      follow_feature_extraction_max_image_size: true
      fallback_max_image_size: 4096
    reconstruction:
      backend: global
  eval:
    enabled: false
    holdout_fraction: 0.15
    patch_count: 10
    eval_steps: [5000, 10000, 15000]
    metrics: [psnr, ssim, lpips]
    target_image_source: training_undistorted
    immutable_results: true
```

The exact field names can change. The important semantics are:

- feature size is the primary SfM resolution knob;
- undistortion follows feature size by default when feature size is set;
- eval target source and dimensions are recorded explicitly and should match the held-out undistorted patch images used by LFS;
- eval is a main pipeline capability, not only an ablation helper.

## Test Plan

### Unit Tests

- [x] Config validation for feature type and ALIKED options.
- [x] CLI override parsing for `null`, `1024`, `2048`, feature type, mapper backend, and eval settings.
- [x] COLMAP feature extractor command for SIFT full-res, SIFT 2048, ALIKED 1024.
- [x] COLMAP undistorter effective max size resolution.
- [x] LFS config generation with eval/save steps.
- [x] Metrics parser for old and new headers.
- [x] LPIPS missing-value handling.
- [x] Holdout 10% selection and expressible `--test-every`.
- [x] Stage 1 grid generation: 12 variants per dataset.
- [x] Stage 2 grid generation: patch-size x splat-count only, using chosen SfM source.
- [x] Immutable ledger backup/upsert behaviour.

### Local Mocked Integration

- [x] Fake COLMAP test proving intrinsics and main extraction both receive feature `max_image_size`.
- [x] Fake COLMAP test proving undistortion follows feature max size.
- [x] Fake LFS test proving eval rows at 5k/10k/15k are parsed.
- [x] Fake ablation run proving one job creates manifest rows, holdout manifests, eval dataset manifests, metrics, and final summaries.

### Local Real Smoke

Use a scratch config derived from `configs/test.yml`.

1. 500-iteration end-to-end smoke:
   - [x] one tiny SIFT/full-res or `2048` run;
   - [x] `advanced.eval.enabled: true`;
   - [x] one or two patches only if possible;
   - [x] verify outputs and logs.

2. 500-iteration ALIKED smoke:
   - [x] same test dataset;
   - [x] feature type `ALIKED`;
   - [x] verify model availability and COLMAP registration.

3. 15k eval-cadence smoke:
   - [x] one patch;
   - [x] eval/save steps `[5000, 10000, 15000]`;
   - [x] verify all metric rows exist;
   - [x] verify checkpoint/PLY artefacts at configured steps.

4. Undistorted held-out eval proof:
   - [x] verify metric target image dimensions are recorded.
   - [x] **NEW** verify a `1024` or `2048` variant trains and evaluates on held-out undistorted patch images at the same effective size.
   - [x] **NEW** verify eval manifests say the target is not raw distorted images and not a separate full-resolution undistorted tree.

5. LPIPS proof:
   - [x] **NEW** run one tiny local eval that writes a real non-placeholder LPIPS value, or leave LPIPS out of formal ranking until it is implemented.

### Local Docker Smoke

- [x] Rebuild local Docker image if dependencies or LFS assets change.
- [x] Run `configs/docker-test.yml` or a scratch derivative on `test_dataset`.
- [x] Verify COLMAP, LFS, metrics, and optional SOG still work.
- [x] Verify no missing ALIKED model inside container.
- [x] Verify LPIPS dependency/output inside container; current LFS metrics still do not emit LPIPS.
Ben adding notes for codex: note we put our docker image online somewhere for nebius? so this will need updating or doing again and nebius needs to grab the right one I think?

### Nebius Smoke

1. Preflight-only or 500-iteration smoke:
   - [x] `test_dataset`;
   - [x] one SIFT variant;
   - [x] one ALIKED variant if local ALIKED passed;
   - [x] upload and verify exit marker for preflight;
   - [x] 500-iteration `splat.train,splat.eval` smoke with main-pipeline eval outputs.

2. 15k eval-cadence smoke:
   - [x] one dataset and one patch or up to two patches;
   - [x] verify per-iteration metrics and resource samples;
   - [x] confirm S3/object storage output shape.

2.5. Formal undistorted held-out eval smoke:
   - [ ] **NEW** after the local held-out eval proof passes, run at most one cheap Nebius smoke proving the same target-source labelling if Docker or worker behaviour changed.

3. One representative full job:
   - [ ] one dataset;
   - [ ] one Stage 1 variant;
   - [ ] up to 10 eval patches serially;
   - [ ] use this to tighten time/cost estimate before broad launch.
   - [ ] **NEW** inspect the final pilot status, uploaded S3 artefacts, SfM warnings, selected sparse model, patch/eval outputs, and VM deletion before deciding whether the representative run counts as useful evidence.

Ben adding notes for codex: note nebius pulls code from github fo this repo right? so changes made after we move to nebius may not be captured if we are not commiting and pushing to github? Do you haev permissions to do this? please make sure to do this i f possible or say if its is going to be an issue.

## Launch Gates

Do not launch the broad grid until all are true:

- [x] Unit tests pass.
- [x] Local fake integration tests pass.
- [x] Local real 500-iter smoke passes.
- [x] Local 15k eval-cadence smoke passes.
- [x] Local Docker smoke passes.
- [x] Nebius 500-iter smoke passes.
- [x] Nebius 15k eval-cadence smoke passes.
- [x] ALIKED model handling is deterministic in Docker/Nebius. Docker smoke proved baked extractor and matcher ONNX model paths in image `61ada12`; Nebius ALIKED smoke `aliked_feat_test_dataset_491bf3d_20260704T001231Z` used those paths and completed without runtime model download.
- [x] Eval target image source and dimensions can be materialised and recorded.
- [x] **NEW** Formal metrics use held-out undistorted patch images at the variant's effective training resolution, not raw distorted images or a separate full-resolution tree.
- [x] **NEW** LPIPS is either genuinely computed and verified end-to-end, or excluded from formal ranking with missing values kept blank.
- [ ] **NEW** The representative pilot has finished, uploaded outputs, deleted its VM, and its absurd reprojection-error warning has been investigated before its result is trusted.
- [x] Output roots, ledgers, and immutable attempt policy have been reviewed.
- [x] Public-IP quota and intended parallelism are checked immediately before launch.

## Open Decisions For Review

- [x] Should Stage 1 pick a single overall SfM winner across all datasets, or one winner per dataset for Stage 2? Answer: 1 across all
- [x] Should eval target be raw distorted images, a separate full-resolution undistorted tree, or the same undistorted image set used by LFS training? Answer: use held-out images from the same undistorted patch image set used by LFS training.
- [x] Should LPIPS be implemented inside LFS, through an existing LFS path, or as an external Python metric after rendering? Answer: if we can do all eval in lfs then yes do this as its best support, so eval eery 5k iters and use all three metrics including lpips. if we can't then second option is do it speratelty.
- [x] Should ALIKED use `n16rot` or `n32` by default? Answer: use `n32` for the quality-first sweep; keep `n16rot` configurable as the faster/lighter option.
- [x] Should preemptible H100s be allowed for formal sweeps, given interruption risk? never use preemptible.
- [x] Should Stage 1 run all 48 jobs immediately, or first run a reduced 2-dataset pilot to estimate incremental mapper and ALIKED cost? Answer: runa  two stage pilot once you get to it, using watch job skill the whole wway (and pick a faster run, i.e dont start with incremental mapper). then report back before i give go ahead to do all.
- [x] Should selected final visual runs include cleanup/merge/SOG, while formal sweeps stop after eval? Answer: do not do the clean up merge and sog. i may choose to do it later myself, but dont do it for now. but keep it compatible in case i do later.

## Recommended Implementation Order

1. WP0: freeze explicit AIMS baseline and variant diff checks.
2. WP1: implement resolution semantics and undistortion following.
3. WP6 partial: expose LFS eval/save steps and parse per-step metrics.
4. WP8: keep holdouts to 10% and improve Stage 2 reuse semantics.
5. WP7: update metric schema and determine real LPIPS source.
6. WP4/WP5: converge eval into main pipeline and settle undistorted held-out eval.
   - **NEW** make target-source naming and manifests explicit enough that no raw/full-resolution target confusion remains.
7. WP2: add ALIKED and test model handling.
8. WP3: formalise mapper sweep.
9. WP9/WP10/WP11: regenerate ablation grids, Nebius worker convergence, and immutable records.
   - **NEW** add selected sparse model id/path to completed manifests and ledgers.
10. Run the local and Nebius smoke gates.
11. Launch a reduced pilot.
12. Launch broad Stage 1 only after pilot review.

BEN adding notes for codex: note, do all stuff locally first before attempting on nebius if a nebius job will require a docker rebuild. we do not want to keep doing slow docker rebuilds. 

## Notes From Prior Failures To Guard Against

- Do not accidentally run full vocab-tree matching when the intended setting is sequential matching with vocab-tree loop detection only.
- Do not let new defaults leak into old/baseline-equivalent configs.
- Do not rely on empty vocab-tree files when loop detection is enabled.
- Do not use symlinked image roots that make COLMAP record unexpected relative paths.
- Do not forget `PYTHONPATH` for inline worker Python snippets.
- Do not pass secrets on visible SSH command lines.
- Do not assume stopped VMs are free of all cost; disks and quota remain.
- Do not assume H100 quota is the same as public-IP quota.
- Do not report metrics from downsampled undistorted patch images as full-resolution metrics.
- Do not treat `lpips=0.0` as valid unless the metric implementation is proven.
- see /home/ben/encode/code/3DReefs/scratch/experiments/troubleshooting_nebius.md for other things to wtach out for, this is a doc where we kept roubleshooting tips from old nebius jobs. anything new that comes up from nebius should be added to this.

## Working Notes

2026-07-03 implementation pass:

- Implemented WP0 foundation in `experiments/ablations/ablation_config.yml`, `src/reefs/experiments/ablations/config.py`, `src/reefs/experiments/ablations/runner.py`, and `src/reefs/experiments/ablations/ledger.py`.
- The ablation config now has an explicit `aims_baseline_overrides` block and 12 Stage 1 SfM variants per dataset: 3 image sizes x 2 feature types x 2 mapper backends. Across datasets 1-4 this gives 48 SfM jobs.
- AIMS matching is now explicit as sequential matching with loop detection, not a separate full vocab-tree matcher. The manifest records whether a full vocab-tree matcher is actually used.
- Added a Stage 1 variant assertion: generated variants may only differ from the AIMS baseline by image size, feature type, mapper backend, and ALIKED-specific fields. This is intended to catch silent default drift before launch.
- Implemented WP1 resolution semantics in `src/reefs/config/models.py`, `src/reefs/colmap/commands.py`, and `src/reefs/sfm/pipeline.py`.
- Effective undistortion size is now: explicit undistortion size, else feature extraction max size if following is enabled, else fallback 4096.
- `run_manifest.json` now records `effective_sfm_settings` under `sfm.output_paths`, including feature type, feature max image size, effective max features, configured/effective undistortion size, and follow/fallback policy.
- Updated `configs/example.yml` to show the new undistortion follow policy. Dataset configs still explicitly pin `undistortion.max_image_size: 4096`; the ablation variants override this to `null` so they follow feature size.
- Implemented WP2 schema/command foundation for ALIKED: `advanced.sfm.feature_extraction.type`, `advanced.sfm.feature_extraction.aliked.model`, `max_num_features`, `min_score`, and optional `n16rot_model_path` / `n32_model_path`.
- Correction: the system `colmap` on PATH reports COLMAP 3.9.1, but the repo/test config uses `/home/ben/software/3dreefs/colmap-4.0.4-cuda-cudss/bin/colmap`, which reports COLMAP 4.0.4 commit `9c23f694` and exposes ALIKED. Use the pinned binary for ALIKED tests, not PATH `colmap`.
- Added the main `advanced.eval` config block, default off, with holdout fraction 0.10, patch count 10, eval steps 5000/10000/15000, and metrics PSNR/SSIM/LPIPS. This is schema only so far; first-class pipeline routing for eval is not complete.
- Updated LFS metrics parsing to accept old headers and LPIPS headers. Missing LPIPS stays missing; it is not converted to `0.0`.
- Added `lpips` to splat ledgers and progress reports.
- Fixed a splat-grid naming bug exposed by the 500k cap: `500000` now formats as `500k`, not `0m`.
- Tightened SfM preflight so a real vocab tree is required for sequential loop detection, not only for a standalone `vocab_tree_matcher`. This guards against empty/missing vocab-tree mistakes when loop detection is enabled.
- Updated mocked integration fixtures to explicitly set `matching.mode: vocab_tree` when requesting `sfm.match.vocab_tree`, and to disable loop detection in tests that intentionally do not provide a vocab tree.
- Verification run: `uv run pytest tests/unit` passed, 248 tests.
- Verification run: `uv run pytest tests/integration/test_sfm_mocked_success.py` passed, 11 tests.
- Verification run: materialised a scratch ablation manifest at `scratch/experiments/ablation_manifest_check_o6LAsN/manifest.csv`; it contains 48 SfM job rows plus 36 splat job rows and shows the baseline-diff/key-setting columns.
- ALIKED correction: COLMAP 4.0.4 uses `FeatureExtraction.type` values `ALIKED_N16ROT` and `ALIKED_N32`, plus `AlikedExtraction.n16rot_model_path` / `n32_model_path`; the pipeline now maps user-facing `type: ALIKED` plus `aliked.model` to the correct COLMAP enum.
- ALIKED matching correction: matchers now emit `--FeatureMatching.type ALIKED_BRUTEFORCE` for ALIKED variants. Preflight now requires an ALIKED-compatible vocab-tree path for ALIKED loop detection or vocab-tree matching instead of accepting the SIFT vocab tree.
- Local ALIKED smoke: `scratch/experiments/aliked_colmap_smoke_20260703T200717Z` extracted ALIKED_N32 features for 8/8 images with 512 keypoints per image using pinned COLMAP 4.0.4.
- Local ALIKED SfM smoke: `scratch/experiments/aliked_sfm_smoke_20260703T200930Z` ran ALIKED_N32 extraction, ALIKED_BRUTEFORCE sequential matching, and mapper on 20 images. It produced one sparse model with 10 registered images, 703 points, mean track length 3.78, and mean reprojection error 1.30 px.
- ALIKED asset policy: use `n32` by default for the quality-first sweep and pre-stage ONNX/vocab assets for Docker/Nebius. The local smoke downloaded `aliked-n32.onnx` into `~/.cache/colmap`, which is acceptable for local proof but not acceptable as an unrecorded cloud dependency.
- ALIKED vocab-tree assets are separate files from the current SIFT vocab tree. COLMAP 4.0.4 advertises:
  - `https://github.com/colmap/colmap/releases/download/3.13.0/vocab_tree_faiss_flickr100K_words64K_aliked_n16rot.bin`
  - `https://github.com/colmap/colmap/releases/download/3.13.0/vocab_tree_faiss_flickr100K_words64K_aliked_n32.bin`
  These were not found locally under `/home/ben/encode/data`, `/home/ben/software/3dreefs`, or `~/.cache/colmap` during this pass.
- WP3 warning thresholds: `_sfm_quality_warning()` now uses backend-aware registration thresholds, catches multiple sparse models, graph fragmentation, zero sparse points, and zero mean/median reprojection errors.
- The 20-image ALIKED SfM smoke used COLMAP's incremental `mapper`, so it also serves as a small local incremental smoke. It was direct-COLMAP rather than the full Python pipeline; a pipeline-level smoke is still useful before cloud.
- Nebius preflight smoke `preflight_test_dataset_20e8f82b_20260703T223934Z` completed with `EXIT:0` on image `ff169f0`, Git ref `20e8f82768b799717b31fb9916de874abc9af102`, and verified COLMAP/LFS/splat-transform plus SIFT and ALIKED vocab tree mounts.
- Nebius SIFT feature-extraction smoke `sift_feat_test_dataset_20e8f82_20260703T224633Z` completed with `EXIT:0`, feature type `SIFT`, 436 raw images staged, main `sfm.extract` timing 655.0s, and intrinsics subset extraction/matching/reconstruction complete for both camera groups.
- Nebius ALIKED feature-extraction smoke first attempt `aliked_feat_test_dataset_20e8f82_20260703T230527Z` failed during ALIKED matching because COLMAP guided matching is not supported for ALIKED. Fixed in code by forcing guided matching off for ALIKED.
- Nebius ALIKED rerun `aliked_feat_test_dataset_0df3e12_20260703T231232Z` completed with `EXIT:0`, feature type `ALIKED_N32`, and main `sfm.extract` timing 345.0s. Important caveat: the failed log showed COLMAP also downloads `bruteforce-matcher.onnx` for `ALIKED_BRUTEFORCE`; this means the original Docker model bake was incomplete.
- Fixed ALIKED matcher model determinism in commit `61ada12`: command builders now pass `--AlikedMatching.bruteforce_model_path` from config/env for sequential, vocab-tree, spatial, and cross-camera matching; Docker now bakes `/opt/colmap/models/aliked-bruteforce-matcher.onnx` and sets `ALIKED_BRUTEFORCE_MATCHER_MODEL_PATH`.
- Built and pushed Docker image `cr.eu-north1.nebius.cloud/e00eqkjz0mkvvedmrd/3dreefs:61ada12` with digest `sha256:dc8ddd88f1e8be9149458b36397f0417f9c20ae3ee526f808777c6ee60b99765`. Local container check confirmed all three ALIKED model env vars and files exist.
- Nebius ALIKED deterministic rerun `aliked_feat_test_dataset_491bf3d_20260704T001231Z` completed with `EXIT:0` using image `61ada12` digest `sha256:dc8ddd88f1e8be9149458b36397f0417f9c20ae3ee526f808777c6ee60b99765` and Git ref `491bf3d`. It completed `sfm.feature_extraction`, main `sfm.extract` took 346.2s, matcher commands used `--FeatureMatching.guided_matching 0`, `--FeatureMatching.type ALIKED_BRUTEFORCE`, and `--AlikedMatching.bruteforce_model_path /opt/colmap/models/aliked-bruteforce-matcher.onnx`. Log scan found no `Downloading file from` lines.
- Nebius incremental smoke `incremental_patch_test_dataset_0df3e12_20260703T232540Z` completed with `EXIT:0` through `sfm,splat.patch` using image `ff169f0`, Git ref `0df3e12127fb80c5725edc4711da2ec9312aeec0`, SIFT, and `advanced.sfm.reconstruction.backend=incremental`. It registered 436/436 images, produced one sparse model with 147,920 points, undistorted at effective size 4096, and created two patch folders (`p000`, `p001`). Key timings: main extraction 655.7s, sequential matching 45.6s, cross-camera matching 1.9s, reconstruction 575.6s, undistortion 515.5s, patching 2.5s.
- Worker convergence commit `d4a7f12` removed the bespoke shell-side eval CSV/Markdown writer from `scripts/nebius/run_ablation_worker.sh`. The `EVAL_PATCH_COUNT` branch now runs `splat.train,splat.eval` with `advanced.eval.enabled=true` and `target_image_source=resized_undistorted`, so Nebius eval outputs are the main pipeline eval manifests/metrics rather than a separate shell summary.
- SIFT vs ALIKED feature-count recording: SfM metrics now include keypoint image count, total keypoints, min/median/mean/max keypoints per image, and the progress report shows mean keypoints per image.
- WP9/WP11 traceability hardening: formal ledger upserts now validate status strings against `planned`, `running`, `complete`, `complete_with_warnings`, `failed`, `superseded`, and `archived`.
- WP11 retry hardening: the first ablation command attempt keeps the familiar job directory paths; repeated attempts are written under `jobs/<job_id>/attempts/<timestamp>/`, with `latest_attempt.json` pointing to the active log.
- WP11 warning records: SfM warning classifiers now append structured `warnings.jsonl` rows beside the job records, while `events.jsonl` also records the final row status.
- Verification run: `uv run pytest tests/unit/test_ablation_ledger.py tests/unit/test_ablation_runner.py` passed, 15 tests.
- WP9 scratch-doc archive: added 2026-07-03 archive notices to `scratch/experiments/nebius_remaining_jobs_runbook.md` and `scratch/experiments/experiment_job_matrix.md` so they remain useful history but cannot be mistaken for the current launch plan.
- WP11 scratch reader: added `scratch/experiments/read_ablation_job_records.py` to summarise `jobs/*/run_identity.json`, `latest_attempt.json`, `events.jsonl`, and `warnings.jsonl`. Smoke check on `scratch/experiments/stage2_local_500/output` printed a table; that older output predates most identity fields, so it naturally showed blanks.
- WP4 eval convergence: added shared `src/reefs/eval/lfs.py` for LFS eval attempts. Both main `splat.eval` and ablation splat eval now use the same helper for eval config generation, LFS command execution, status classification, loss history, and metrics parsing.
- Verification run: `uv run pytest tests/unit/test_lfs_commands.py tests/unit/test_ablation_splat_eval.py tests/integration/test_splat_mocked_success.py tests/integration/test_splat_mocked_failures.py` passed, 33 tests.
- WP9 Stage 2 winner manifest: added `stage2-manifest --sfm-variant <variant>` so reviewed Stage 1 winners produce named Stage 2 manifests instead of only the placeholder `best` label. The Stage 2 runner now accepts selected-variant job IDs while retaining `best` compatibility.
- Verification run: generated `scratch/experiments/stage2_manifest_verify_20260703/output/manifest_stage2_sfm_full_sift_global.csv` with 36 planned jobs plus header and `stage2_source_sfm_full_sift_global.json`.
- Correction: the first Stage 2 manifest verification used the default ablation output root and briefly wrote generated review files under `data/experiments/ablations`; those generated files were removed immediately and the verification was rerun under scratch.
- WP5/WP7 report clarity: splat ledgers now include `eval_target_source`, `eval_image_width`, and `eval_image_height`, and progress reports show eval target and size beside PSNR/SSIM/LPIPS so downsampled eval cannot masquerade as full-resolution eval.
- Verification run: `uv run pytest tests/unit/test_ablation_splat_eval.py tests/unit/test_ablation_runner.py tests/integration/test_splat_mocked_success.py` passed, 39 tests.
- Local Docker smoke: rebuilt `3dreefs:local` from current source, then ran `scripts/docker/run_test_dataset_e2e.sh` with `configs/docker-test.yml` on `data/test_dataset`.
- Docker smoke output root: `scratch/experiments/docker_smoke_20260703/e2e/project/runs/docker_smoke_20260703T2245Z`.
- Docker smoke verification: in-container unit smoke tests passed (`20 passed`); all requested stages `sfm,splat,splat.postprocess` completed; Docker COLMAP ran SIFT sequential matching plus cross-camera matching; LFS `6d591a34` trained two 500-iter patches; cleanup, merge, and SOG completed. Key outputs are `splat/merged/merged_splat.ply` (22M) and `splat/merged/merged_splat.sog` (1.1M).
- Docker smoke note: this was a SIFT/configs-docker-test run, so it did not prove ALIKED ONNX/vocab availability inside the container.
- `uv run ruff ...` could not run because `ruff` is not installed in this environment.
- Staged ALIKED vocab-tree assets in Nebius Object Storage next to the existing SIFT asset:
  - SIFT current asset: `s3://3dreefs-ben-eu-north1/input/assets/vocab_tree_faiss_flickr100K_words256K.bin`;
  - ALIKED n16rot: `s3://3dreefs-ben-eu-north1/input/assets/vocab_tree_faiss_flickr100K_words64K_aliked_n16rot.bin`;
  - ALIKED n32: `s3://3dreefs-ben-eu-north1/input/assets/vocab_tree_faiss_flickr100K_words64K_aliked_n32.bin`.
- Extended Nebius Stage 1 launch/worker staging so `ALIKED_N16ROT_VOCAB_TREE_S3_URI` and `ALIKED_N32_VOCAB_TREE_S3_URI` default to those assets, are passed to the VM, downloaded by the worker, and mounted read-only at `/input/aliked_n16rot_vocab_tree.bin` and `/input/aliked_n32_vocab_tree.bin`.
- Remaining major work at this point in the historical pass: real LFS eval/save cadence, `metrics_long.csv` writing, proving whether LFS emits real LPIPS, ALIKED model policy, local real smokes, Docker rebuild/publish, Nebius smokes, immutable run identity/events, and the reduced two-dataset pilot. Superseded note: separate full-resolution undistorted eval target generation is no longer part of the formal ablation plan after the 2026-07-04 eval-target decision.
- Nebius note: if workers pull code from GitHub, these changes must be committed and pushed before a Nebius run can see them. If Docker image contents change, the image must be rebuilt/pushed and the worker config must point at the new image tag/digest.
- WP6 partial: ablation eval now writes attempt-specific `lfs_eval_config.json` files that preserve any base LFS JSON while overriding `eval_steps`, `save_steps`, `enable_eval`, `enable_save_eval_images`, and `headless`. Step lists are bounded to the requested training horizon and always include the final iteration.
- WP6 partial: ablation eval now writes root-level `metrics_long.csv` rows for every parsed LFS eval iteration while keeping `results_splat.csv` as the final rollup. Verification run: `uv run pytest tests/unit/test_lfs_commands.py tests/unit/test_ablation_metrics.py tests/unit/test_ablation_splat_eval.py` passed, 20 tests.
- WP8: holdout manifests now record the ordered patch image-set hash and selected image count. Existing canonical holdout files are validated and treated as immutable inputs; if the patch image set changes, the comparable run fails instead of silently picking new holdouts.
- WP8: Stage 1 holdout paths remain per SfM job, while Stage 2 holdout paths are shared across comparable splat variants by dataset, SfM source label, patch size, and patch id. Verification run: `uv run pytest tests/unit/test_ablation_splat_eval.py tests/unit/test_ablation_runner.py` passed, 18 tests.
- WP4/WP5 partial: moved reusable holdout and eval dataset construction to `src/reefs/eval/holdout.py` and left a compatibility wrapper under `src/reefs/experiments/ablations/holdout.py`.
- WP5 guard: eval dataset manifests now record `target_image_source`, camera source, image source, and whether patch training images were used. Historical note: at this point the ablation eval path refused `full_resolution_undistorted` until a real full-resolution target builder existed; this formal target direction was superseded by the later decision to use held-out images from the same undistorted patch image set. Verification run: `uv run pytest tests/unit/test_ablation_splat_eval.py tests/unit/test_ablation_runner.py tests/unit/test_lfs_commands.py tests/unit/test_ablation_metrics.py` passed, 29 tests.
- WP5 manifest tightening: eval dataset manifests now include metric implementation, holdout image count, and best-effort per-holdout image dimensions. Verification run: `uv run pytest tests/unit/test_ablation_splat_eval.py` passed, 14 tests.
- WP9/WP11 partial: ablation-launched pipeline commands now write per-job `run_identity.json`, `command_record.json`, and append-only `events.jsonl` before/around command execution. Verification run: `uv run pytest tests/unit/test_ablation_runner.py` passed, 6 tests.
- WP4: added explicit main-pipeline `splat.eval` stage. It is not included in the normal `splat` alias, requires `advanced.eval.enabled: true`, writes holdout manifests, LFS eval config, eval dataset manifests, `metrics_long.csv`, `metrics_final.csv`, and per-patch eval status under `splat/eval/`. Verification run: `uv run pytest tests/integration/test_splat_mocked_success.py tests/unit/test_splat_resume.py tests/unit/test_splat_pipeline.py tests/unit/test_splat_config.py tests/unit/test_sfm_config.py` passed, 28 tests.
- Eval failure handling fix: `splat.eval` now fails the pipeline if any LFS eval attempt returns non-zero, while still writing `eval_status.json`, `eval_manifest.json`, and metrics CSV stubs for diagnosis. `write_lfs_eval_config()` now requires a real base LFS optimisation JSON; the earlier tiny generated JSON was not accepted by LFS. Verification run: `uv run pytest tests/unit/test_lfs_commands.py tests/integration/test_splat_mocked_success.py tests/unit/test_ablation_splat_eval.py` passed, 28 tests.
- Local real 500-iteration smoke passed under `scratch/experiments/local_eval_train_smoke_20260703/project/runs/local_eval_train_smoke_500` using steps `sfm,splat.patch,splat.train,splat.eval`, p000 only, and LFS base config `/home/ben/software/3dreefs/src/lichtfeld-studio-6d591a34/eval/mcmc_optimization_params.json`. Exit code 0. Stages through `splat.eval` complete. `p000` trained 500/500 iterations in 11.88s with final loss 0.3620 and 3,586 splats. Eval used 27 train + 3 val cameras, wrote rows at 250 and 500 iterations, and final metrics were PSNR 11.645953, SSIM 0.367978, no LPIPS column/value, 3,586 Gaussians. Key outputs: `splat/eval/metrics_long.csv`, `splat/eval/metrics_final.csv`, `splat/eval/eval_manifest.json`, and `splat/eval/patches/p000/attempt_1/metrics.csv`.
- Local 15k eval-cadence smoke passed under `scratch/experiments/local_eval_15k_smoke_20260703/project/runs/local_eval_15k_smoke`, reusing the verified scratch SfM/patch artefacts and running steps `splat.train,splat.eval` for p000 only. Exit code 0. Normal p000 training completed 15,000/15,000 iterations in 553.54s with final loss 0.1031 and 1,000,000 splats. Eval completed in 603.10s with 27 train + 3 val cameras and metric rows at 5k, 10k, and 15k:
  - 5,000: PSNR 16.508928, SSIM 0.520096, 32,139 Gaussians.
  - 10,000: PSNR 16.767138, SSIM 0.529903, 368,440 Gaussians.
  - 15,000: PSNR 16.440069, SSIM 0.512638, 1,000,000 Gaussians.
  LFS `metrics.csv` has columns `iteration,psnr,ssim,time_per_image,num_gaussians`; there is no LPIPS column in this build. Checkpoints were written at eval/save steps, but observed PLY files were final outputs only: `splat_15000.ply` for train and eval. Key outputs: `splat/eval/metrics_long.csv`, `splat/eval/metrics_final.csv`, `splat/eval/patches/p000/attempt_1/metrics.csv`, `metrics_report.txt`, and `checkpoints/checkpoint.resume`.
- Local normal non-eval smoke passed under `scratch/experiments/local_noneval_train_smoke_20260703/project/runs/local_noneval_train_smoke_500` using steps `splat.train` only, p000 only, 500 iterations. Exit code 0. LFS logged `Using all 30 images for training (no evaluation)`, completed 500/500 iterations in 11.66s, final loss 0.4007, and 3,586 splats. This confirms the explicit `splat.eval` stage did not disturb the old standalone training path.
- WP9/WP11 traceability update: ablation-launched pipeline commands now write pre-launch `effective_config.yml` and `effective_config_overrides.json` beside `run_identity.json` and `command_record.json`. Ledger `upsert_row()` now creates a timestamped backup under `ledger_backups/` before replacing an existing completed row. Verification run: `uv run pytest tests/unit/test_ablation_ledger.py tests/unit/test_ablation_runner.py` passed, 9 tests. Commit: `bbb2502 Record ablation effective configs and ledger backups`.
- WP9 review helper: added `ablation_experiment.py dry-run`, which prints and writes `dry_run_summary.json` with Stage 1/Stage 2 job counts, known SfM upper-bound hours, unknown splat/cost placeholders pending pilot resource samples, and planned output roots. Verification run: `uv run pytest tests/unit/test_ablation_runner.py` passed, 8 tests. Commit: `442bf73 Add ablation dry-run summary`.
- Manifest verification: ran `PYTHONPATH=src uv run python -m reefs.experiments.ablations.runner manifest --config scratch/experiments/ablation_manifest_verify_20260703/ablation_config.yml` against a scratch config/output root. It wrote `manifest.csv`, `plan.md`, `progress.md`, and empty result ledgers under `scratch/experiments/ablation_manifest_verify_20260703/output`. Manifest has 84 rows total: 48 Stage 1 SfM jobs and 36 Stage 2 splat jobs.
- Docker ALIKED model staging: added pinned downloads for `aliked-n16rot.onnx` and `aliked-n32.onnx` under `/opt/colmap/models`, exposed as `ALIKED_N16ROT_MODEL_PATH` and `ALIKED_N32_MODEL_PATH`. The command builder now falls back to those env vars when config paths are unset.
- Docker ALIKED smoke: rebuilt `3dreefs:local` and verified both ONNX files and env vars in the image. A first ALIKED extraction smoke caught missing runtime cuDNN visibility (`libcudnn.so.9`), then Docker `LD_LIBRARY_PATH` was extended to include the pinned Python/NVIDIA library directories.
- Docker ALIKED smoke passed after the runtime-library fix: `scratch/experiments/docker_smoke_20260703/aliked/extract_ldpath.log` ran COLMAP `FeatureExtraction.type=ALIKED_N32` on 4 test images, produced 4 keypoint rows and 512 total keypoints. The ONNX Runtime `ScatterND` warnings were non-fatal.
- Dockerfile hygiene: moved the ALIKED model download layer after the expensive LFS build layer so future ONNX/model-path edits do not invalidate the LFS compile cache.
- WP5 historical full-resolution eval branch: added `advanced.eval.full_resolution_undistorted_images_dir` and enabled `target_image_source: full_resolution_undistorted` to build eval datasets from a separate full-resolution undistorted image tree while preserving patch sparse/camera geometry and relative names.
- WP5 historical full-resolution guard/manifest behaviour: that branch failed if the separate full-resolution undistorted image root was missing and recorded `uses_patch_training_images: false`, `is_full_resolution_eval: true`, target dimensions, and resize/crop policy.
- WP5 historical limitation: this path used LFS's train-with-eval mode on the separate full-resolution undistorted eval dataset. It proved larger target images could be passed to LFS, but it is no longer the formal ablation eval direction.
- WP5 historical real smoke: copied the 500-iter scratch smoke to `scratch/experiments/local_eval_train_smoke_20260703/project/runs/local_eval_fullres_500`, generated 30 two-times-larger full-resolution-undistorted images under `scratch/experiments/local_eval_train_smoke_20260703/project/full_resolution_undistorted_p000_2x`, and ran `splat.eval` for `p000` at 250/500 iterations. The eval manifest recorded holdout widths around 8192 px and `metrics_final.csv` ended at PSNR 11.663968, SSIM 0.368726, LPIPS missing, 3,586 Gaussians. Superseded note: useful as a compatibility experiment only, not formal ablation semantics.
- Verification run: `uv run pytest tests/unit/test_ablation_splat_eval.py tests/integration/test_splat_mocked_success.py tests/unit/test_sfm_config.py` passed, 32 tests.
- WP7 ranking semantics: added explicit splat-row ranking where complete rows come first, SSIM and PSNR are maximised, LPIPS is minimised when present, and missing LPIPS does not beat a real LPIPS value when other quality metrics match. The progress report now includes a compact ranked "Best Splat Rows" section.
- Verification run: `uv run pytest tests/unit/test_ablation_metrics.py tests/unit/test_ablation_runner.py` passed, 23 tests.
- WP6 save-cadence decision: for the formal ablation ledgers, per-step eval is represented by LFS `metrics.csv` rows and checkpoint/resume artefacts at configured eval/save steps. Current LFS does not emit a separate PLY at every save step in the observed 15k run, so the pipeline will keep final PLY/SOG output as final artefacts only unless we later need visual inspection at intermediate steps.
- WP5 evaluator branch decision at that time: because LFS accepted the separate full-resolution-undistorted eval dataset path in the real 500-iter smoke, a separate renderer/evaluator was not required for that historical smoke gate. Superseded note: formal ablation eval now uses held-out images from the same undistorted patch image set.
- WP7 LPIPS branch decision: the current LFS build does not emit LPIPS, so the implemented path is missing-aware parsing/reporting and ranking. A real LPIPS dependency remains deferred until a separate Python metric/evaluator is deliberately added.
- Docker image `cr.eu-north1.nebius.cloud/e00eqkjz0mkvvedmrd/3dreefs:1e696e2` was built and pushed with digest `sha256:2bdc0c27d8af69b68990356adb015bb9428e5b695f39199fbb4ca0c4fa0021ca`. Local container verification confirmed `/opt/lichtfeld-studio/eval/mcmc_optimization_params.json` and all baked ALIKED model env paths exist.
- Nebius 500-iteration eval smoke `nebius_500_eval_test_dataset_1e696e2_20260704T004514Z` passed with `EXIT:0`, image `1e696e2`, Git ref `1e696e2`, and main-pipeline stages through `splat.eval` complete. It restored the incremental SfM/patch source, regenerated `splat.patch` because the restored metadata lacked `selected_images`, selected `p001`, trained for 500 iterations in 82.49s, and evaluated in 24.12s.
- Nebius 500 eval outputs verified from S3 under `s3://3dreefs-ben-eu-north1/experiments/ablations/smoke/runs/nebius_500_eval_test_dataset_1e696e2_20260704T004514Z/`: `run_status.json`, `timings.json`, `effective_config.yml`, logs, `splat/eval/eval_manifest.json`, `metrics_long.csv`, `metrics_final.csv`, holdout manifest, eval dataset manifest, attempt log, checkpoint, and final PLY are present. `metrics_long.csv` has rows at 250 and 500 iterations; final row is PSNR 10.651679, SSIM 0.339673, LPIPS missing, 18,348 Gaussians. Caveat: the resumed worker sync uploaded about 7.2 GiB because it re-uploaded restored SfM/staged artefacts as well as the new eval outputs; output-shape/cost review should consider narrowing smoke sync scope.
- WP10 Nebius worker hardening: `run_ablation_worker.sh` now refuses to create an empty SIFT vocab-tree placeholder when `VOCAB_TREE_S3_URI` is missing, writes synced `worker_identity.json` with `IMAGE_NAME`, `GIT_REF`, resolved commit, config, dataset, run id, and worker mode, and supports `WORKER_MODE=preflight_only` to verify config/raw image/vocab/tool availability before a full job.
- WP10 review: launcher secret handling, raw-image mount, `--project-dir /scratch/3dreefs/project`, Stage 1 ablation entrypoint, and delete-after-worker-upload ordering are preserved. The old `EVAL_PATCH_COUNT` shell-side summary path still exists and remains a cleanup item.
- Verification run: `bash -n scripts/nebius/run_ablation_worker.sh && bash -n scripts/nebius/launch_worker_vm.sh && bash -n scripts/nebius/launch_stage1_job.sh` passed.
- Nebius preflight passed: `preflight_test_dataset_20e8f82b_20260703T223934Z` uploaded `EXIT:0`, `preflight_result.json`, and `worker_identity.json` under `s3://3dreefs-ben-eu-north1/experiments/ablations/smoke/runs/preflight_test_dataset_20e8f82b_20260703T223934Z/`. It used image `cr.eu-north1.nebius.cloud/e00eqkjz0mkvvedmrd/3dreefs:ff169f0`, Git commit `20e8f82768b799717b31fb9916de874abc9af102`, config `configs/docker-test.yml`, COLMAP `3.14.0.dev0`, and saw all SIFT/ALIKED vocab assets.
- Nebius SIFT feature-extraction smoke passed: `sift_feat_test_dataset_20e8f82_20260703T224633Z` uploaded `EXIT:0` and run records under `s3://3dreefs-ben-eu-north1/experiments/ablations/smoke/runs/sift_feat_test_dataset_20e8f82_20260703T224633Z/`. It used SIFT with 4096 effective features; `sfm.extract` took 655.02s after two intrinsics precalc passes. Warning: raw images were staged to COLMAP-safe names because cross-camera matching cannot parse whitespace, so the sync uploaded the staged-image copy as well.
- Nebius ALIKED feature-extraction first attempt failed: `aliked_feat_test_dataset_20e8f82_20260703T230527Z` uploaded `EXIT:1`. COLMAP aborted in `sfm.intrinsics.match.sequential` because `FeatureMatching.guided_matching=1` is not supported for `ALIKED_BRUTEFORCE`. Fix committed and pushed as `0df3e12 Disable guided matching for ALIKED`.
- Nebius ALIKED feature-extraction rerun passed: `aliked_feat_test_dataset_0df3e12_20260703T231232Z` uploaded `EXIT:0` under `s3://3dreefs-ben-eu-north1/experiments/ablations/smoke/runs/aliked_feat_test_dataset_0df3e12_20260703T231232Z/`. It used ALIKED_N32 with baked ONNX model paths, ALIKED vocab-tree loop detection, and guided matching forced off. Main `sfm.extract` took 344.99s after two intrinsics precalc passes.
- Nebius 15k eval-cadence smoke passed: `nebius_15k_eval_test_dataset_1e696e2_20260704T005501Z` uploaded `EXIT:0` under `s3://3dreefs-ben-eu-north1/experiments/ablations/smoke/runs/nebius_15k_eval_test_dataset_1e696e2_20260704T005501Z/`. It used image/Git `1e696e2`, restored the incremental SfM/patch source, selected p001, trained for 15,000 iterations in 811.97s, and evaluated in 764.86s. `metrics_long.csv` has rows at 5k, 10k, and 15k: 5k PSNR 16.981827 / SSIM 0.529605 / 164,769 Gaussians; 10k PSNR 17.949858 / SSIM 0.549830 / 200,000 Gaussians; 15k PSNR 18.036402 / SSIM 0.554827 / 200,000 Gaussians. LPIPS remains missing because this LFS build does not emit it.
- Nebius resource-sampler proof passed after commit `fa95ee9`: `nebius_500_resource_test_dataset_fa95ee9_20260704T012944Z` uploaded `EXIT:0`, complete `run_status.json`, normal logs, `effective_config.yml`, `run_manifest.json`, `worker_identity.json`, eval manifests, `metrics_long.csv`, `metrics_final.csv`, `resource_samples.csv`, and `resource_summary.json`. The sampler recorded 6 samples with peak RAM 4,398 MiB, peak VRAM 2,683 MiB, peak GPU utilisation 41%, and peak GPU power 217.91 W. This verifies the worker-side resource-sample path; the earlier 15k run predates this sampler commit, so its metrics cadence is verified but its own resource samples are not.
- Nebius 500 resource proof metrics ended at PSNR 10.717906, SSIM 0.344129, LPIPS missing, 18,348 Gaussians. Training took 82.15s and eval 18.76s. As with the other resumed smokes, the upload included about 7.2 GiB because restored SfM/staged artefacts were synced as part of the run root; this is acceptable for the smoke but should be narrowed before broad repeated eval runs if storage/upload cost becomes painful.
- WP11 verification rerun: `uv run pytest tests/unit/test_ablation_ledger.py tests/unit/test_ablation_runner.py tests/unit/test_ablation_splat_eval.py tests/unit/test_ablation_metrics.py` passed, 42 tests. This covers atomic ledger writes with backups, valid status states, timestamped retry attempt directories, `latest_attempt.json`, `run_identity.json`, `command_record.json`, append-only `events.jsonl`, `warnings.jsonl`, metrics-long upserts, and missing-aware LPIPS parsing/ranking.
- WP5 historical ablation eval fix: removed the stale `full_resolution_undistorted` refusal in `src/reefs/experiments/ablations/splat_eval.py`, passed `advanced.eval.full_resolution_undistorted_images_dir` through to the shared eval dataset builder, fixed a latent retry bug that referenced an undefined `log_path`, and made eval-target dimension parsing handle the actual manifest mapping form. Verification run: `uv run pytest tests/unit/test_ablation_splat_eval.py tests/unit/test_ablation_runner.py tests/unit/test_ablation_metrics.py` passed, 40 tests. Commit: `6a04318 Allow ablation eval full-res targets`. Superseded note: formal ablation eval no longer targets this separate full-resolution tree by default.
- WP5 historical downsample/full-resolution proof passed under `scratch/experiments/local_downsample_fullres_eval_proof_20260704/project/runs/downsample_fullres_eval_500`. The patch `selected_images` were downsampled to max width 1024 with relative names preserved; the separate full-resolution-undistorted eval target tree kept the same 30 relative names at max width 8192. Running `splat.eval` for p000 at 250/500 iterations completed with `target_image_source: full_resolution_undistorted`, `uses_patch_training_images: false`, `is_full_resolution_eval: true`, and holdout dimensions recorded as 8192 px wide. Final metrics were PSNR 11.662162, SSIM 0.373884, LPIPS missing, 3,586 Gaussians. Superseded note: this remains a diagnostic compatibility proof, not the formal eval procedure. The first proof attempts caught two procedural gotchas: `python -m reefs.cli` is a no-op because the module defines `app` but does not call it, and `configs/test.yml` pointed at older LFS v0.5.2 which lacks `--no-save-eval-images`; the successful run used `PYTHONPATH=src uv run python -c 'from reefs.cli import app; app()'` plus the `lichtfeld-studio-6d591a34` binary/config overrides.
- First representative Stage 1 Nebius pilot attempt `pilot_dataset4_sfm_1024_sift_global_a59e5fc_20260704T014629Z` failed before SfM with `EXIT:1`. The Stage 1 worker injected `advanced.sfm.preflight.colmap_target_version=5f35f398` into the variant overrides only, so `_assert_stage1_variant_scope()` correctly rejected it as a non-sweep setting change. The VM deleted cleanly and `nebius compute instance list --format json` returned `{}` afterwards. Fix: update the generated Nebius Stage 1 config so the Docker/COLMAP compatibility override is also present in `aims_baseline_overrides`, preserving the intended variant diff guard.
- Public-IP launch gate check: immediately before and during the representative pilot, `nebius compute instance list --format json` and `nebius vpc allocation list --format json` showed exactly one running worker VM, one assigned private IPv4, and one assigned public IPv4 (`89.169.112.66`) for `computeinstance-e00hdvg0fbta93a7p8`. The known quota note remains that public IPv4 fanout should be capped at three workers unless the quota is raised.
- Representative Stage 1 Nebius pilot rerun `pilot_dataset4_sfm_1024_sift_global_ef07b36_20260704T015518Z` is running with image `1e696e2`, Git ref `ef07b36`, dataset `dataset4`, variant `sfm_1024_sift_global`, and output prefix `s3://3dreefs-ben-eu-north1/experiments/ablations/pilot/runs/pilot_dataset4_sfm_1024_sift_global_ef07b36_20260704T015518Z/`. Health check around 2026-07-04 02:07 UTC showed the Stage 1 guard passed and the active main pipeline command is in `sfm` with `advanced.sfm.feature_extraction.max_image_size=1024`, `FeatureExtraction.type=SIFT`, `advanced.sfm.reconstruction.backend=global`, AIMS intrinsics-refine flags, cross-camera pair generation enabled, and `advanced.splat.patching.max_cameras=400`.
- 2026-07-04 final eval-target decision: formal ablation eval should use held-out images from the same undistorted patch image set used for LFS training. Do not use raw distorted images. Do not require a separate full-resolution undistorted target tree for formal metrics.
- 2026-07-04 correction to the previous audit correction: the Stage 1 undistortion follow policy is correct. `null` feature extraction should undistort/train/eval at fallback `4096`; `2048` and `1024` feature variants should undistort/train/eval at the same smaller size.
- 2026-07-04 audit follow-up: LPIPS still needs real implementation/proof. Current parser support is missing-aware only; LFS's event-side `0.0f` placeholder is not a valid LPIPS metric.
- 2026-07-04 audit follow-up: selected sparse model id/path should be carried into completed manifests and SfM ledgers. The code selects the largest registered-image model, but result rows currently expose only the sparse model count.
- 2026-07-04 audit follow-up: the representative pilot must be inspected after completion before it is used for cost or quality estimates, because the live refinement analyser showed an implausible reprojection-error value.
- Backup before this update: `scratch/experiments/ablation_pipeline_redesign_plan.backup_20260704_after_audit.md`.
- 2026-07-04 WP5/WP7/WP11 update: formal ablation eval now canonicalises `resized_undistorted` and `patch_undistorted` to `training_undistorted`; the default main eval target is `training_undistorted`; the ablation config refuses `full_resolution_undistorted` unless `validation.allow_full_resolution_target: true` is explicitly set for a diagnostic run; the Nebius eval worker now passes `advanced.eval.target_image_source=training_undistorted`.
- 2026-07-04 ledger update: `results_splat.csv`, main-pipeline `splat/eval/metrics_long.csv`, ablation `metrics_long.csv`, and final eval metric rows now carry `eval_target_source`, `eval_image_width`, and `eval_image_height`. Completed SfM rows now carry `selected_sparse_model_id`, `selected_sparse_model_path`, and `selected_sparse_model_copy_path`.
- 2026-07-04 LPIPS ranking guard: LFS LPIPS parsing remains present and missing-aware, but formal `rank_splat_rows()` ignores LPIPS by default until a real non-placeholder LPIPS source is implemented and deliberately enabled. Progress Markdown now says LPIPS is displayed when present but excluded from formal ranking until end-to-end verification.
- 2026-07-04 verification: `uv run pytest tests/unit/test_ablation_metrics.py tests/unit/test_ablation_splat_eval.py tests/unit/test_ablation_runner.py tests/integration/test_splat_mocked_success.py tests/integration/test_sfm_mocked_success.py` passed, 66 tests. `uv run pytest tests/unit` passed, 285 tests.
- 2026-07-04 real LPIPS implementation: added `lpips==0.1.4` through `uv`, enabled LFS saved eval comparison images whenever `lpips` is requested, computes external LPIPS with `lpips.LPIPS(net='alex')` from the same `eval_step_<iteration>` held-out GT/render images used for PSNR/SSIM, merges values back into LFS `metrics.csv`, and writes `lpips_metrics.json`.
- 2026-07-04 LPIPS local benchmark: `scratch/experiments/lpips_benchmark_20260704/project/runs/local_lpips_benchmark_20260704T102143Z` ran `splat.eval` only on copied scratch `p000` for 500 iterations. It saved 3 comparison PNGs at each of steps 250 and 500, downloaded the AlexNet weights once to the local torch cache, and completed `splat.eval` in 10.62s. Final metrics: PSNR 11.640286, SSIM 0.166009, LPIPS 0.901703, 3,586 Gaussians, eval target `training_undistorted`, representative eval size 1024x900.
- 2026-07-04 LPIPS verification: `uv run pytest tests/unit/test_eval_lpips.py tests/unit/test_lfs_commands.py tests/unit/test_ablation_metrics.py tests/unit/test_ablation_splat_eval.py tests/integration/test_splat_mocked_success.py` passed, 48 tests. Then `uv run pytest tests/unit tests/integration/test_splat_mocked_success.py tests/integration/test_sfm_mocked_success.py` passed, 310 tests.
- 2026-07-04 Docker refresh for LPIPS: built and pushed `cr.eu-north1.nebius.cloud/e00eqkjz0mkvvedmrd/3dreefs:ac6ffaa` after the Python dependency change. Local image/registry digest is `sha256:faac5261bef90d4d9e97abc2173c31c510820e86dc6eb8240453599e61a05e3b`; container import check printed `lpips present`, `torch 2.12.1+cu130`, `torchvision 0.27.1+cu130`. Nebius worker and Stage 1 launcher defaults now point at this tag.
