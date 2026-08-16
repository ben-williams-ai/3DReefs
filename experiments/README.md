# Reproducing the 3DReefs ablations

This directory contains the experiments reported with *A Protocol for
Producing 3D Gaussian Splats of Large Seabed Habitats*. Use the main pipeline
for complete site models; use these runners only to reproduce controlled
parameter comparisons.

## Experimental design

Stage 1 compares SfM feature resolution (1024, 2048 or full), feature type
(SIFT or ALIKED), and mapper (global or incremental). Each scientifically
successful reconstruction is evaluated through fixed held-out splat patches.

Stage 2 reuses the winning Stage 1 source—1024-pixel SIFT features with the
global mapper—and compares training resolution (1024, 2048 or full), cameras
per patch (200, 400 or 800), and Gaussian budget (500K, 1M or 2M). Evaluation
targets are always full-resolution undistorted images.

Canonical, publication-ready tables and figures are kept in:

```text
experiments/results/
  stage1/stage1_results.csv
  stage2/stage2_results.csv
```

Only verified successful rows belong in these master CSVs. Partial runs,
worker logs, checkpoints and large model artefacts remain outside Git.

## Reproducible environment

All formal sweeps were run on Nebius with one NVIDIA H100 SXM GPU, 16 vCPUs,
200 GB RAM and a 960 GiB network-SSD boot disk per job. The repository Docker
image pins the Ceres, COLMAP, LichtFeld Studio, Python and evaluation stack.
Record both the Git commit and registry image digest for every run.

Before launching experiments, complete the main
[installation and data preparation](../README.MD) and the
[Docker/Nebius setup](../docs/workflows/docker-nebius.md). You need:

- one raw-image bundle per dataset in Nebius Object Storage;
- the SIFT vocabulary tree in Object Storage;
- a pushed, GPU-verified Docker image;
- Nebius and AWS CLIs authenticated on the control machine; and
- enough H100 quota for the jobs launched concurrently.

Use placeholders or environment variables for bucket, subnet and registry
identifiers. Never commit credentials.

## Inspect the sweep before spending GPU time

The scientific grid is defined in `ablations/ablation_config.yml`. Generate
the manifests and run a simulated smoke before launching cloud workers:

```bash
uv run python experiments/ablations/ablation_experiment.py manifest
uv run python experiments/ablations/ablation_experiment.py stage2-manifest \
  --sfm-variant sfm_1024_sift_global
uv run python experiments/ablations/ablation_experiment.py smoke --simulate
```

The simulation checks orchestration only; it is not a scientific result.

## Nebius execution

Set shared cloud variables in the shell, not in tracked files:

```bash
export SUBNET_ID=<subnet-id>
export BUCKET=<bucket-name>
export IMAGE_NAME=cr.eu-north1.nebius.cloud/<registry-id>/3dreefs:<tag>
export IMAGE_DIGEST=sha256:<digest>
export GIT_REF=$(git rev-parse origin/main)
export VOCAB_TREE_S3_URI=s3://$BUCKET/input/assets/vocab_tree_faiss_flickr100K_words256K.bin
export DELETE_ON_FINISH=true
```

The wrappers verify that the Git commit is pushed, the registry digest matches,
the source/output prefix is safe, and uploaded results can be read back before
deleting a VM.

### Stage 1: one SfM variant

```bash
export DATASET_NAME=dataset1
export STAGE1_VARIANT=sfm_1024_sift_global
scripts/nebius/launch_stage1_job.sh
```

Valid variant names are listed under `sfm_variants` in
`ablations/ablation_config.yml`. Stage 1 uses a 24-hour SfM limit; reaching it
is a scientifically valid timeout outcome and must not be silently retried
with relaxed settings.

### Create the reusable Stage 2 source

Create this bundle once per dataset, then reuse it for every Stage 2 probe:

```bash
export DATASET_NAME=dataset1
scripts/nebius/launch_stage2_source_job.sh
```

Do not rerun SfM for each splat setting. A Stage 2 batch accepts only a source
whose `source_complete.json` says `verified_complete`.

### Stage 2: one resolution/patch-size batch

```bash
export DATASET_NAME=dataset1
export SOURCE_BUNDLE_URI=s3://$BUCKET/experiments/ablations/stage2_sources/runs/<source-run-id>
export TRAINING_RESOLUTION=2048
export PATCH_SIZE=200
export SPLAT_COUNTS=500000,1000000,2000000
scripts/nebius/launch_stage2_batch_job.sh
```

One worker trains the requested Gaussian budgets for that resolution and patch
size. Use a new empty output prefix for every launch. Keep
`DELETE_ON_FINISH=true`; preserve a failed VM only long enough to recover
otherwise irreplaceable outputs.

## Verification and recovery

A launcher exit code alone is insufficient. Before accepting a run, verify its
worker exit marker, `run_status.json`, expected metric rows and Object Storage
readback. Treat incomplete patch counts and hard training failures explicitly
in the results ledger.

If a Stage 2 source already has a valid database and refined sparse model but
failed during undistortion or upload, recover it without rerunning SfM:

```bash
export DATASET_NAME=dataset1
export RUN_ID=<new-empty-run-id>
export RESUME_FROM_S3_URI=s3://$BUCKET/<failed-source-prefix>
scripts/nebius/launch_stage2_source_recovery_job.sh
```

Operational failure modes and tested fixes are recorded in
[`docs/troubleshooting.md`](../docs/troubleshooting.md). Do not improvise a
partial container command that bypasses image, preflight or upload gates.

## Consolidate and plot results

Copy only the small, verified run summaries from Object Storage into a staging
directory, archive the previous canonical CSV, then consolidate and inspect the
diff before replacing it:

```bash
uv run python scripts/consolidate_stage2_results.py --help
uv run python scripts/plot_stage1_ablation_interaction.py
uv run python scripts/plot_stage2_ablation_interactions.py
```

The plotting scripts read the canonical CSVs under `experiments/results/` and
write the publication figures beside them. Never point them at a directory
that mixes successful, partial and superseded attempts.
