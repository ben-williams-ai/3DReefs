# Docker And Nebius Workflow

This workflow packages the local 3DReefs toolchain in one GPU container and
writes generated data under scratch instead of `data/`.

## Local Docker Setup

Install Docker Engine and NVIDIA Container Toolkit on the host, then verify:

```bash
sudo scripts/docker/install_host_docker_ubuntu.sh
nvidia-smi
docker --version
nvidia-ctk --version
```

Build the image:

```bash
scripts/docker/build_image.sh
```

The image contains the heavy runtime and Python dependencies from the `uv.lock`
used at build time. Its COLMAP is built against custom CUDA/cuDSS-enabled Ceres
so bundle adjustment must not silently fall back to CPU. Rebuild it when the
Dockerfile, Ceres/COLMAP/LFS/splat-transform, system packages, or Python
dependencies change. Do not rebuild it for new datasets, run ids, configs, or
ordinary Python code changes.

If a CUDA architecture causes a build failure on a target GPU, rebuild with an
explicit list:

```bash
CUDA_ARCHITECTURES='89;90;100;120' scripts/docker/build_image.sh
```

The default Ceres/COLMAP refs are:

```text
CERES_REF=bac1127f9ef672405bd0d2d9c84e809ae89bd239
COLMAP_REF=5f35f39868de8694913e39a44adcdd8c983504ed
```

## Local GPU And End-To-End Check

Check GPU visibility inside the container:

```bash
scripts/docker/check_gpu.sh
scripts/docker/verify_colmap_gpu_ba.sh
```

After any SFM run, scan the COLMAP log in strict mode:

```bash
LOG_FILE=/path/to/project/runs/<run_id>/logs/colmap.log \
scripts/docker/verify_colmap_gpu_ba.sh
```

Run the full local test dataset, saving output under ignored scratch:

```bash
scripts/docker/run_test_dataset_e2e.sh
```

Default output:

```text
scratch/docker-e2e/<timestamp>/project/runs/docker_test_<timestamp>/
```

The script mounts `data/test_dataset` read-only and symlinks only
`raw_images/` into the scratch project, so local dataset outputs are not
modified.

## Run A Job From Git

Normal jobs should run a Git ref inside the prebuilt image. By default the
runner uses `GIT_REF=main`; set `GIT_REF` to a commit SHA for reproducible cloud
runs. The Git ref must include the config schema expected by the mounted job
config.

```bash
DATASET=/path/to/dataset \
VOCAB_TREE=/path/to/vocab_tree.bin \
CONFIG=/path/to/job.yml \
OUT_ROOT=/path/to/scratch/job_001 \
RUN_ID=job_001 \
scripts/docker/run_job_from_git.sh
```

The runner mounts:

```text
/input/dataset       read-only dataset
/input/vocab_tree.bin read-only vocabulary tree
/job/config.yml      read-only job config
/scratch/3dreefs     writable code checkout, project symlink, and run outputs
```

Configs used with this runner should use container paths:

```yaml
project:
  dir: /scratch/3dreefs/project
tools:
  colmap_bin: /opt/colmap/bin/colmap
  lfs_bin: /opt/lichtfeld-studio/build-release/LichtFeld-Studio
  splat_transform_bin: splat-transform
  vocab_tree_path: /input/vocab_tree.bin
advanced:
  sfm:
    preflight:
      colmap_target_version: "5f35f398"
```

## Nebius Shape

Use Object Storage as the source of truth and VM local disk as scratch:

```text
Object Storage input -> local scratch -> container run -> Object Storage output
```

Keep the cloud runner controlled by environment variables:

```bash
SCRATCH_ROOT=/scratch/3dreefs
INPUT_DATASET_URI=s3://bucket/input/dataset
VOCAB_TREE_URI=s3://bucket/input/vocab_tree.bin
OUTPUT_URI=s3://bucket/experiments/run-id/jobs/job-id
RUN_ID=job-id
```

On a Nebius VM, sync or mount Object Storage inputs onto local disk, pull the
prebuilt image from a registry, then run `scripts/docker/run_job_from_git.sh`
with those local paths. Do not rebuild the image on every VM; rebuild once only
when the toolchain or locked Python dependencies change. Start with one
container over one GPU VM. After the local Docker E2E and one Nebius VM pass,
add Terraform fan-out for ablation jobs.

Current intended GPU targets: L40S, H100, H200, and RTX PRO 6000.
