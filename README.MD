# 3DReefs

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux-FCC624.svg?logo=linux&logoColor=black)](#requirements)
[![Licence: BSD 3-Clause](https://img.shields.io/badge/licence-BSD%203--Clause-blue.svg)](LICENSE)

An end-to-end pipeline for reconstructing large seabed habitats as 3D Gaussian
splats. 3DReefs combines COLMAP structure from motion (SfM), spatial patching,
LichtFeld Studio training, Wildflow cleaning and merging, and optional SOG
export.

**Paper:** *A Protocol for Producing 3D Gaussian Splats of Large Seabed
Habitats* — link coming soon.<br>
**Datasets:** download links coming soon.

## Pipeline

```text
camera images -> SfM -> undistortion -> optional colour restoration
              -> camera patches -> Gaussian training -> clean -> merge -> SOG
```

Each run is resumable and records its effective configuration, logs and status
under `<project.dir>/runs/<run-id>/`. The cleaned, complete merged PLY remains
the authoritative model; SOG is used to compress the outputs for interactive viewing - we recommend uploading the SOG file of your model to supersplat within your web browser to view the final 3D Gaussian Splat.

## Requirements

3DReefs targets Linux with an NVIDIA GPU. The reproducible Docker image is the
recommended installation because COLMAP and LichtFeld Studio require compiled
CUDA toolchains.

The reference systems used for development and experiments were:

| Environment | Tested hardware |
| --- | --- |
| Local development and post-processing | Ubuntu 24.04; AMD Ryzen Threadripper PRO 9965WX (24 cores); NVIDIA RTX PRO 6000 Blackwell Max-Q (96 GB VRAM); 512 GB RAM |
| Nebius ablation worker | One NVIDIA H100 SXM GPU; 16 vCPUs; 200 GB RAM; 960 GiB network-SSD boot disk |

These are tested configurations, not minimum requirements. Runtime, storage and
VRAM needs depend strongly on image count, resolution and scene extent.

The controlled software stack is Python 3.12, [uv](https://docs.astral.sh/uv/),
[COLMAP](https://colmap.github.io/) 4.0.4 (`9c23f694`),
[LichtFeld Studio](https://github.com/MrNeRF/LichtFeld-Studio) at `6d591a34`,
Wildflow 0.1.5 and
[`splat-transform`](https://github.com/playcanvas/splat-transform) 1.10.2.
Changing these versions can change scientific results.

## Installation

### Recommended: Docker

Install Docker Engine and the NVIDIA Container Toolkit, then build and verify
the complete pinned toolchain:

```bash
scripts/docker/build_image.sh
scripts/docker/check_gpu.sh
scripts/docker/verify_colmap_gpu_ba.sh
```

Run the bundled end-to-end smoke dataset after building:

```bash
scripts/docker/run_test_dataset_e2e.sh
```

See [Docker and Nebius workflow](docs/workflows/docker-nebius.md) for host
installation, mounted paths and reproducible cloud execution.

### Native development environment

Install Python 3.12 and
[uv](https://docs.astral.sh/uv/getting-started/installation/), then install the
locked Python environment (including Wildflow):

```bash
uv sync --frozen --dev
cp .env.example .env
```

For a native pipeline run, install compatible CUDA builds of COLMAP and
LichtFeld Studio plus `splat-transform`, then set their paths in `.env`. The
Dockerfile is the reference build recipe and exact source of version pins.

SIFT loop detection also requires a COLMAP vocabulary tree. Download
`vocab_tree_faiss_flickr100K_words256K.bin` from the
[COLMAP vocabulary-tree models](https://demuc.de/colmap/) and set
`VOCAB_TREE_PATH` in `.env`. The file is not included in this repository.

Check the command-line interface:

```bash
uv run main.py --help
```

## Prepare a dataset

Create one project directory per survey. Put single-camera images directly in
`raw_images/`, or preserve one subdirectory per synchronised camera:

```text
my_dataset/
  raw_images/
    cam1/
      image_000001.jpg  # Any filenames work; capture order should sort correctly.
      image_000002.jpg
    cam2/
      image_000001.jpg
      image_000002.jpg
```

Keep original filenames, full image resolution and metadata. Camera folders
should cover the same time interval and have consistently ordered images.
3DReefs detects single- versus multi-camera layouts and checks dimensions and
camera-source consistency before expensive work begins.

Copy `configs/example.yml` and edit its mandatory sections first: choose the
colour-restoration mode, set `project.dir`, and supply the external tool and
vocabulary-tree paths directly or through `.env`:

```bash
cp configs/example.yml configs/my_dataset.yml
```

The advanced section already contains the recommended defaults from the
cross-dataset ablations: 1024-pixel SIFT feature extraction with COLMAP's
global mapper, followed by 2048-pixel training with at most 200 cameras and
2 million Gaussians per patch. Most users should begin with these settings and
only change them for a documented hardware or experimental reason.

## Run the full pipeline

This command reconstructs, trains every valid patch, cleans and merges the
patches, and exports SOG:

```bash
uv run main.py \
  --config configs/my_dataset.yml \
  --run-id my_dataset_v1 \
  --steps sfm,splat,splat.postprocess \
  --resume-policy overwrite
```

Use a unique run ID. To continue an interrupted run, repeat the command with
`--resume-policy resume`; do not overwrite expensive partial outputs.

The same pipeline can be run one stage at a time with the same run ID:

```bash
# Validate images, configuration and external tools.
uv run main.py --config configs/my_dataset.yml --run-id my_dataset_v1 --steps sfm.preflight

# Estimate cameras and sparse 3D structure, then undistort the images.
uv run main.py --config configs/my_dataset.yml --run-id my_dataset_v1 --steps sfm --resume-policy resume

# Divide the reconstruction into spatial camera groups.
uv run main.py --config configs/my_dataset.yml --run-id my_dataset_v1 --steps splat.patch --resume-policy resume

# Train every selected Gaussian patch.
uv run main.py --config configs/my_dataset.yml --run-id my_dataset_v1 --steps splat.train --resume-policy resume

# Clean, merge and export the trained patches.
uv run main.py --config configs/my_dataset.yml --run-id my_dataset_v1 --steps splat.postprocess --resume-policy resume
```

For Docker jobs from a pinned Git commit, use
`scripts/docker/run_job_from_git.sh`; its required mounts and variables are
documented in the [cloud workflow](docs/workflows/docker-nebius.md).

## Colour restoration

Colour restoration never changes the raw images used for SfM. It creates a
run-local corrected copy of the undistorted images consumed by splat training,
so camera geometry and colour treatment remain independently reproducible.

For an existing dataset profile, set this in the dataset config:

```yaml
colour_restoration:
  mode: profile
  profile_path: colour-profiles/my_dataset-colour.json
  overwrite: false
```

Then run the normal pipeline; the profile is applied automatically before
training. To create a profile interactively, use:

```bash
uv run main.py colour profile create \
  --config configs/my_dataset.yml \
  --output configs/colour-profiles/my_dataset-colour.json
```

`gray_world` provides an unattended baseline, while `manual` opens the editor
for run-specific adjustments. See `uv run main.py colour --help` for the
available commands.

## Nebius

Nebius jobs use Object Storage as the durable source of truth and disposable
GPU VM disks as scratch space. Install the
[Nebius CLI](https://docs.nebius.com/cli/install), authenticate it, configure
AWS CLI access to Object Storage, and push the Docker image once. Ordinary
production runs use `scripts/nebius/launch_production_job.sh`; paper ablations
use the guarded experiment wrappers.

The complete setup, storage layout, image pinning, success checks and safe VM
deletion rules are in [Docker and Nebius workflow](docs/workflows/docker-nebius.md).
Never place cloud credentials in configs, shell scripts or Git.

## Reproduce the paper experiments

The ordinary pipeline above is for complete models. The Stage 1 SfM and Stage
2 Gaussian-splat ablations use separate runners, held-out image evaluation and
result ledgers. See [experiments/README.md](experiments/README.md) for their
design, commands and canonical results.

## Tests

Run the local test suite with:

```bash
uv run pytest
```

GPU/toolchain integration checks are separate:

```bash
scripts/docker/check_gpu.sh
scripts/docker/verify_colmap_gpu_ba.sh
scripts/docker/run_test_dataset_e2e.sh
```

## Citation and licence

Citation details will be added when the paper is public. 3DReefs is released
under the [BSD 3-Clause License](LICENSE).
