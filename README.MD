# 3DReefs

Tools and workflows for reconstructing large reef areas with photogrammetry and
Gaussian splatting.

## Set up

This project expects a Linux workstation with an NVIDIA GPU. COLMAP is used for
photogrammetry, LichtFeld Studio is used for Gaussian splat training, and
`splat-transform` is used for SOG conversion when SOG output is enabled.

Install the Python project environment with `uv`:

```bash
uv sync
```

Copy the environment template and set local tool/resource paths:

```bash
cp .env.example .env
```

The real `.env` file is gitignored. Public configs use environment variables
such as `${COLMAP_BIN}`, `${LFS_BIN}`, `${SPLAT_TRANSFORM_BIN}`, and
`${VOCAB_TREE_PATH}` so private machine paths stay out of the repository.


### Hardware And System Requirements

- NVIDIA GPU (TODO add minimum vram needed)
- Working NVIDIA driver.
- CUDA Toolkit for source builds.
- C/C++ build tools, CMake, Ninja, Git, and vcpkg dependencies required by the
  upstream projects.

Check that Linux can see the GPU:

```bash
nvidia-smi
```

Check that the CUDA compiler is available if building from source:

```bash
nvcc --version
```

### Tested Tool Versions

These were the latest stable releases available when this setup was written.
Newer versions may work, but command-line options and build requirements can
change.

- COLMAP `4.0.4` for SfM
- LichtFeld Studio `v0.5.2` for splatting
- `@playcanvas/splat-transform` / `splat-transform` `v1.10.2` for SOG conversion

## Prepare Your Data

Create one project directory per dataset. The only required input folder is
`raw_images/`.

For a single-camera dataset, put the images directly in `raw_images/`:

```text
my_dataset/
  raw_images/
    image_0001.jpg
    image_0002.jpg
    image_0003.jpg
```

For a multi-camera dataset, put one folder per camera inside `raw_images/`:

```text
my_dataset/
  raw_images/
    cam1/
      image_0001.jpg
      image_0002.jpg
    cam2/
      image_0001.jpg
      image_0002.jpg
```

The pipeline should infer multi-camera mode from these camera subfolders. If
recoloured images are used for undistortion, add `recoloured_images/` with the
same folder layout and the same filenames as `raw_images/`.

## Pipeline Foundation Check

Feature 1 provides the foundation CLI and preflight records only. It validates
config files, derives project-local paths, checks image layout, records CLI
overrides, validates configured external tools, and writes run records. It does
not run COLMAP reconstruction, matching, undistortion, patching, LFS training,
cleanup, compression, or merge stages.

Run the foundation check with:

```bash
uv run main.py --config configs/example.yml
```

Common invocation patterns:

```bash
uv run main.py --config configs/example.yml --project-dir /path/to/project
uv run main.py --config configs/example.yml --advanced.splat.train.num_iters 20000
uv run main.py --config configs/example.yml --steps foundation --resume-policy resume
```

The public config layout keeps mandatory `project` and `tools` sections first;
all other settings live under `advanced`. Normal paths are derived from `project.dir`: `raw_images/`, optional
`recoloured_images/`, and `runs/`. Public example configs use placeholders; make
local copies or `.env` values for machine-specific paths.

Each foundation run writes records under `<project.dir>/runs/<run_id>/`:

```text
effective_config.yml
cli_overrides.json
run_manifest.json
run_status.json
timings.json
logs/pipeline.log
```

`logs/warnings.log` is created only when warnings occur.
These records are created as soon as a run starts and are updated after each
stage, so interrupted long runs can be inspected and resumed.

If prior partial outputs are detected, resume/overwrite decisions are gathered
during preflight before any requested step starts. Non-interactive runs must use
an explicit `--resume-policy`.

Resume a known interrupted run in place with `--run-id`:

```bash
uv run main.py \
  --config configs/datasets/dataset_01.yml \
  --run-id <run_id> \
  --steps sfm.undistort \
  --resume-policy overwrite
```

This reuses `<project.dir>/runs/<run_id>/` instead of creating a new run
directory.

Resume happens at pipeline stage boundaries. For example, if sequential matching
finished but vocabulary-tree matching did not, rerun the same run with
`--steps sfm.match.vocab_tree`. If undistortion was interrupted, rerun
`--steps sfm.undistort --resume-policy overwrite`; the partial generated
undistortion output is cleared before COLMAP restarts that stage.

## COLMAP SfM Pipeline

Feature 2 runs COLMAP SfM from the same entrypoint. It uses raw images for
feature extraction, matching, and sparse reconstruction. If
`project.recolour_images` is true, recoloured images are validated up front and
used only for undistortion.

Run the SfM stages with:

```bash
uv run main.py --config configs/example.yml --steps sfm --resume-policy overwrite
```

Default SfM behaviour:

- preflight validates image layout, per-camera dimensions, required COLMAP
  subcommands, and vocabulary-tree resources before heavy work starts.
- intrinsics are estimated on a selected image subset, then passed into the full
  reconstruction while final intrinsics refinement remains off by default.
- matching runs sequential matching followed by vocabulary-tree matching.
- reconstruction uses COLMAP `global_mapper` by default.
- undistortion writes images and sparse intrinsics under
  `<project.dir>/runs/<run_id>/sfm/undistorted/`.
- dense point cloud and mesh generation are disabled by default.

Useful lightweight check:

```bash
uv run main.py --config configs/example.yml --steps sfm.preflight --resume-policy overwrite
```

This validates the configured dataset and COLMAP resources without running
feature extraction, matching, reconstruction, or undistortion.

## Splat Patching And Training

Feature 3 consumes a completed Feature 2 run. For splat-only commands, pass the
existing SfM run id so the command reuses `<project.dir>/runs/<run_id>/` instead
of creating a fresh run directory without undistorted SfM outputs.

Generate patches from an existing SfM run:

```bash
uv run main.py \
  --config configs/test.yml \
  --run-id <sfm_run_id> \
  --steps splat.patch \
  --resume-policy overwrite
```

Default patching behaviour:

- validates `sfm/undistorted/images` and `sfm/undistorted/sparse` first.
- exports a text sparse copy for patch planning when COLMAP undistortion produced
  binary sparse files only.
- runs camera-pose outlier filtering before patching when enabled.
- writes patch datasets under `splat/patches/p000/`, including
  `patch_metadata.json`, `sparse/0/`, `selected_images/`, and
  `patch_diagnostics/`.
- never starts LFS unless `splat.train` is requested.

Train one existing patch with a short smoke run:

```bash
uv run main.py \
  --config configs/test.yml \
  --run-id <sfm_run_id> \
  --steps splat.train \
  --advanced.splat.train.patch_ids "[p000]" \
  --advanced.splat.train.num_iters 500 \
  --resume-policy overwrite
```

Training runs one patch at a time. Patch-level status is written to
`splat/patches/<patch_id>/splat/training_status.json`, the run-level training
summary is written to `splat/training/training_manifest.json`, and LFS stdout and
stderr are streamed to `logs/lfs.log` plus the patch-local `run.log`.

Existing patch or training outputs are resolved before any splat work starts.
Use `--resume-policy resume` to reuse valid existing training statuses, or
`--resume-policy overwrite` to regenerate/retrain requested outputs.


### Install COLMAP

Follow the official COLMAP installation guide:

- <https://colmap.github.io/install.html>

For this workflow, build COLMAP with CUDA support to enable GPU acceleration
during SfM. If using GPU bundle adjustment, Ceres Solver also needs CUDA and
cuDSS support:

- <https://colmap.github.io/faq.html?highlight=cuda>

After installing, confirm:

```bash
colmap -h
colmap help | grep -E 'global_mapper|mapper|bundle_adjuster|patch_match_stereo'
```

`colmap -h` should report `with CUDA`.

### Download A Vocabulary Tree

The default SfM matching strategy uses sequential matching followed by
vocabulary-tree matching, so local configs must point to a valid vocabulary tree
file before those matching stages can run. Public example configs should use a
placeholder path; local configs should use the downloaded file path.

### Install LichtFeld Studio

Follow the official Linux build instructions:

- <https://github.com/MrNeRF/LichtFeld-Studio/wiki/Build-Instructions-%E2%80%90-Linux>

After installing, confirm:

```bash
LichtFeld-Studio --help
LichtFeld-Studio --version
```

### Install splat-transform

Install the PlayCanvas splat transform CLI for SOG conversion:

```bash
npm install -g @playcanvas/splat-transform
```

After installing, confirm:

```bash
splat-transform --version
splat-transform --help
```

### Our system

The pipeline has been tested on the following set up:

- Ubuntu 24.04.4 LTS
- Linux kernel 6.17.0-29-generic
- AMD Threadripper PRO 9965WX
- NVIDIA RTX PRO 6000 Blackwell, 96 GB VRAM
- NVIDIA driver 580.159.03
- CUDA Toolkit 12.8
- GCC/G++ 14.2.0
- CMake 4.2.1
- Ninja 1.11.1

# TODO:
- Add minimum VRAM guidance + guidance on selecting patch size given img sizes and VRAM. add calculator to figure out what patch size should given gpu vram?
- Add more on data collection: link to wildflow guide, state images should be sequential and gaps in data hurt output.
- Add link to download vocab tree.
