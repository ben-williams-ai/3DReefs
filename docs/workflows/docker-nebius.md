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

If a CUDA architecture causes a build failure on a target GPU, rebuild with an
explicit list:

```bash
CUDA_ARCHITECTURES='89;90;100;120' scripts/docker/build_image.sh
```

## Local GPU And End-To-End Check

Check GPU visibility inside the container:

```bash
scripts/docker/check_gpu.sh
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

Start with one container over one GPU VM. After the local Docker E2E and one
Nebius VM pass, add Terraform fan-out for ablation jobs.

Current intended GPU targets: L40S, H100, H200, and RTX PRO 6000.
