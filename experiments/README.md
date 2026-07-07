# Nebius Experiment Setup

This note explains how to run 3DReefs experiments on Nebius using one H100 VM per job. It records the setup used for the first end-to-end smoke run, why each piece exists, and the checks that avoid the mistakes we already hit.

The intended flow is:

```text
control machine -> Nebius Object Storage -> ephemeral H100 VM -> Docker worker -> Object Storage results -> VM deleted
```

The Docker image contains the 3DReefs runtime: COLMAP, Ceres, LichtFeld Studio, `splat-transform`, Python, and project dependencies. The VM bootstrap only handles cloud plumbing: download the dataset tarball, pull the image, run the job, upload outputs, and delete the VM.

## What You Need

- A Nebius project with H100 quota.
- Nebius CLI installed and logged in on the control machine.
- AWS CLI v2 available on your local/control machine for checking Nebius Object Storage access. Worker VMs install it automatically.
- Docker available on the machine used to build and push the image.
- An SSH public key, normally `~/.ssh/id_ed25519.pub`.
- A Nebius Container Registry image for this repo.
- An Object Storage bucket containing the dataset tarballs.

Check the active Nebius project:

```bash
nebius config get parent-id
```

Check Object Storage access:

```bash
aws --version
aws s3 ls s3://<BUCKET>/input/datasets/ \
  --endpoint-url https://storage.eu-north1.nebius.cloud
```

If this returns `NoCredentials`, create or rotate an Object Storage access key in Nebius IAM, then configure AWS CLI:

```bash
aws configure set region eu-north1
aws configure set endpoint_url https://storage.eu-north1.nebius.cloud
aws configure set aws_access_key_id "<AWS_ACCESS_KEY_ID>"
aws configure set aws_secret_access_key "<AWS_SECRET_ACCESS_KEY>"
```

Do not put real key values in this repository. If a key is pasted into chat, logs, or a tracked file, rotate it.

## Object Storage Layout

Each dataset is stored as a compressed raw-image bundle:

```text
s3://<BUCKET>/input/datasets/<DATASET_NAME>/
  manifest.json
  raw_images.tar.zst
  raw_images.tar.zst.sha256
```

Inside `raw_images.tar.zst`, the directory must unpack to:

```text
raw_images/
  cam1/
  cam2/
  cam3/
```

The worker verifies `raw_images.tar.zst.sha256`, extracts the tarball on the VM, mounts `raw_images/` directly into the Docker container, and uploads job outputs to:

```text
s3://<BUCKET>/experiments/ablations/runs/<RUN_ID>/
```

For sequential loop detection, use the FAISS vocab tree uploaded to:

```text
s3://<BUCKET>/input/assets/vocab_tree_faiss_flickr100K_words256K.bin
```

For a new bucket, upload it with:

```bash
aws s3 cp /path/to/vocab_tree_faiss_flickr100K_words256K.bin \
  s3://<BUCKET>/input/assets/vocab_tree_faiss_flickr100K_words256K.bin \
  --endpoint-url https://storage.eu-north1.nebius.cloud
```

## Build And Push The Docker Image

Log in to Nebius Container Registry:

```bash
nebius iam get-access-token |
  docker login cr.eu-north1.nebius.cloud --username iam --password-stdin
```

Build the image:

```bash
export IMAGE_NAME="cr.eu-north1.nebius.cloud/<REGISTRY_ID>/3dreefs:<TAG>"
scripts/docker/build_image.sh
```

Push it:

```bash
docker push "$IMAGE_NAME"
```

Important: the image must include `mesa-vulkan-drivers`. Without that package, `splat-transform sog` can fail on Nebius with Vulkan/WebGPU errors even though SfM, training, cleanup, and PLY merge succeed.

## Launch A Smoke Job

Use the control-side launcher. It creates a VM, logs into the registry from the VM, copies a private env file to `/run`, deletes that file before starting the worker, waits for the worker, uploads outputs, and deletes the VM by default.

First choose the subnet. If you do not know it, list subnets in the Nebius console or CLI and pick the subnet in the same region as the bucket and registry:

```bash
export SUBNET_ID="<VPC_SUBNET_ID>"
```

Then launch the smoke dataset:

```bash
export BUCKET="<BUCKET>"
export IMAGE_NAME="cr.eu-north1.nebius.cloud/<REGISTRY_ID>/3dreefs:<TAG>"
export JOB_ID="nebius_test_dataset_e2e"
export RUN_ID="$JOB_ID"
export DATASET_NAME="test_dataset"
export CONFIG_IN_REPO="configs/docker-test.yml"
export STEPS="sfm,splat,splat.postprocess"
export GIT_REF="$(git rev-parse HEAD)"
export VOCAB_TREE_S3_URI="s3://<BUCKET>/input/assets/vocab_tree_faiss_flickr100K_words256K.bin"
export AWS_ACCESS_KEY_ID="$(aws configure get aws_access_key_id)"
export AWS_SECRET_ACCESS_KEY="$(aws configure get aws_secret_access_key)"
export DELETE_ON_FINISH=true

scripts/nebius/launch_worker_vm.sh
```

Why these variables matter:

- `SUBNET_ID`: tells Nebius where to place the VM.
- `BUCKET`: where datasets and outputs live.
- `IMAGE_NAME`: exact Docker image the VM should run.
- `JOB_ID` and `RUN_ID`: human-readable job and output names.
- `DATASET_NAME`: selects `input/datasets/<DATASET_NAME>/`.
- `CONFIG_IN_REPO`: selects the pipeline config inside the Git checkout.
- `STEPS`: controls which pipeline stages run.
- `GIT_REF`: pins the code used inside the VM.
- `VOCAB_TREE_S3_URI`: enables real sequential loop detection.
- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`: allow the VM to download inputs and upload outputs.
- `DELETE_ON_FINISH=true`: removes the VM and its boot disk after completion.

## Verify The Run

Check the exit marker:

```bash
aws s3 cp s3://<BUCKET>/experiments/ablations/runs/<RUN_ID>/<RUN_ID>.exit - \
  --endpoint-url https://storage.eu-north1.nebius.cloud
```

Expected success:

```text
EXIT:0
```

List the uploaded outputs:

```bash
aws s3 ls s3://<BUCKET>/experiments/ablations/runs/<RUN_ID>/ \
  --recursive \
  --endpoint-url https://storage.eu-north1.nebius.cloud
```

Check the pipeline status and logs:

```bash
aws s3 cp s3://<BUCKET>/experiments/ablations/runs/<RUN_ID>/run_status.json - \
  --endpoint-url https://storage.eu-north1.nebius.cloud

aws s3 cp s3://<BUCKET>/experiments/ablations/runs/<RUN_ID>/logs/colmap.log - \
  --endpoint-url https://storage.eu-north1.nebius.cloud |
  rg -i "gpu|ceres|bundle|Creating SIFT|FeatureMatcherWorker"
```

Expected GPU evidence:

- Feature extraction logs `Creating SIFT GPU feature extractor`.
- Matching logs `Bind FeatureMatcherWorker to GPU device 0`.
- Global mapper command includes `--GlobalMapper.gp_use_gpu 1` and `--GlobalMapper.ba_ceres_use_gpu 1`.
- LichtFeld Studio logs CUDA device initialisation during splat training.

COLMAP may not print a separate "Ceres used CUDA" line. Local and Nebius logs both show the same pattern: the GPU BA flag is passed and Ceres runs, but there is no extra CUDA BA confirmation line.

## Billing And Cleanup

For experiment workers, the desired end state is:

```text
outputs uploaded -> exit marker uploaded -> VM deleted
```

A stopped VM is better than a running VM, but it can still keep charging for the boot disk and it still occupies quota. Use stopped VMs only while debugging. Normal ablation jobs should run with:

```bash
export DELETE_ON_FINISH=true
```

If you intentionally leave a VM for debugging:

```bash
nebius compute instance stop <INSTANCE_ID>
nebius compute instance delete <INSTANCE_ID>
```

Delete it once logs and outputs have been copied to Object Storage.

## Running Real Jobs

For ordinary full-dataset pipeline jobs, change the dataset, config, and run id:

```bash
export DATASET_NAME="dataset3"
export RUN_ID="dataset3_sfm_variant_<NAME>"
export JOB_ID="$RUN_ID"
export CONFIG_IN_REPO="configs/datasets/dataset_03.yml"
export STEPS="sfm,splat,splat.postprocess"
scripts/nebius/launch_worker_vm.sh
```

For the current Stage 1 full-resolution-eval ablation sweep, prefer the Stage 1 wrapper:

```bash
export DATASET_NAME="dataset1"
export STAGE1_VARIANT="sfm_2048_sift_global"
export GIT_REF="$(git rev-parse origin/main)"
export IMAGE_NAME="cr.eu-north1.nebius.cloud/e00eqkjz0mkvvedmrd/3dreefs:colmap404-python-eval-20260707"
export OUTPUT_PREFIX="experiments/ablations/stage1_fullres_eval"
export BOOT_DISK_GIB=960
export DELETE_ON_FINISH=true

scripts/nebius/launch_stage1_job.sh
```

The wrapper defaults to the same image, output prefix, 960 GiB network-SSD boot disk, and VM deletion-on-finish. It also injects the validated COLMAP preflight target `9c23f694` for the Stage 1 config.

Stage 1 evaluates each SfM variant with 10 validation patches by default. Current ablation validation compares against `full_resolution_undistorted` targets: SfM writes a second `sfm/undistorted_full_resolution/images` tree for eval, while splat training still uses the normal training-resolution undistorted images.

Keep these resolution settings separate:

- `advanced.sfm.feature_extraction.max_image_size` controls COLMAP SfM feature extraction and reconstruction resolution.
- `advanced.splat.train.max_width` controls splat training and non-full-resolution eval rendering width.
- Setting splat `max_width` to `1024` does not make SfM run at `1024`; set `advanced.sfm.feature_extraction.max_image_size=1024` for a 1024 SfM variant.

Use one VM per ablation job. The ten patch trainings used to evaluate a variant are part of that job; they are not separate cloud jobs unless you deliberately split them later.

For the current experimental plan:

- Stage 1 chooses the best SfM variant by running each SfM setting variant and evaluating it through fixed 10-patch splat training.
- Stage 2 uses the best SfM variant across datasets, then sweeps splat image count per patch, splat count, and optionally max width.
- Keep the max width sweep optional and off by default until the first two factors are stable.


## Porting To Another Cloud

No Nebius credentials are baked into the Docker image. To run on another cloud provider, replace the launcher and storage bootstrap with equivalents for that provider while keeping the same container contract:

```text
/input/dataset/raw_images        read-only raw images
/input/vocab_tree.bin            read-only FAISS vocab tree
/job/config.yml                  read-only pipeline config
/scratch/3dreefs                 writable run/output root
```

The VM must provide NVIDIA GPU access to Docker, enough local disk for the extracted dataset and outputs, and a way to upload the run directory to durable object storage before the machine is deleted.
