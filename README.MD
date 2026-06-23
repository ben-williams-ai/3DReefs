# 3DReefs

Tools and workflows for reconstructing large reef areas with photogrammetry and
Gaussian splatting.

## Set up

This project expects a Linux workstation with an NVIDIA GPU. COLMAP is used for
photogrammetry, LichtFeld Studio is used for Gaussian splat training, and
`wildflow` is used for splat cleanup and cleaned PLY merge. `splat-transform` is
used for final SOG conversion when that output is enabled.

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
- LichtFeld Studio `v0.5.2` is the last tagged release tested, but large
  full-resolution MCMC reef runs should use upstream commit `6d591a34` or later
  until a newer release includes the FastGS bucket-buffer fix.
- `wildflow` `0.1.5` for splat cleanup and cleaned PLY merge
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
colour-restored images are used for splatting, add `recoloured_images/` with the
same folder layout and the same filenames as `raw_images/`. SfM and COLMAP
undistortion always use `raw_images/`.

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

Feature 2 runs COLMAP SfM from the same entrypoint. It always uses raw images
for feature extraction, matching, sparse reconstruction, and COLMAP
undistortion. Colour restoration writes corrected full-resolution images to
`recoloured_images/`, but those corrected images are only for splatting-stage
image inputs and review.

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

## Optional Colour Restoration

Enable colour restoration in a config with:

```yaml
colour_restoration:
  mode: manual  # off | gray_world | manual
  overwrite: false
  start_sfm_immediately: true
```

SfM and COLMAP undistortion always come from `raw_images/`. In `manual` mode and
an interactive terminal, the pipeline opens the PySide6 colour GUI after
preflight. If `start_sfm_immediately` is true, the GUI is opened in the
background and raw-image SfM can run while you edit; if it is false, SfM waits
until the manual colour workflow is resolved. Splatting never starts with
colour-restored inputs while colour restoration is active, applying, incomplete,
or failed.

After applying colour restoration, inspect:

```text
<project.dir>/recoloured_images/
```

This tree mirrors `raw_images/` by relative path and filename. To review the
outputs and continue editing the same run, reopen the GUI:

```bash
uv run main.py colour open --config configs/example.yml --run-id <run_id>
```

You can run colour restoration without SfM, patching, or splatting:

```bash
uv run main.py colour open --config configs/example.yml --run-id <run_id>
uv run main.py colour apply --config configs/example.yml --run-id <run_id>
```

After a complete `<project.dir>/recoloured_images/` tree exists, later
experiments for the same run may reuse it for splatting when
`colour_restoration.overwrite: false` and the saved state proves the outputs are
compatible. The run prints:

```text
Found existing complete same-run recoloured_images/; using it for splatting inputs.
```

This lets you resume splatting for the same completed colour run without
reopening the GUI. COLMAP SfM and COLMAP undistortion still use raw images. Use
`colour open` when you intentionally want to review or continue editing saved
colour state. Set `colour_restoration.overwrite: true` when you intentionally
want to replace the current same-run corrected outputs:

```bash
uv run main.py colour apply --config configs/example.yml --run-id <run_id> --overwrite
```

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
- creates patch bounds with `wildflow.splat.patches`, then uses the current
  single supported camera selector to assign images while keeping the selected
  camera count under `advanced.splat.patching.max_cameras`.
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

## Splat Cleanup, Merge, And SOG

Feature 5 consumes trained patch splats from Feature 3. It cleans each patch PLY,
merges the cleaned patch PLYs into one site-level PLY, then exports one final SOG
from the merged result by default.

Run full post-processing for an existing trained run:

```bash
uv run main.py \
  --config configs/test.yml \
  --run-id <trained_run_id> \
  --steps splat.postprocess \
  --resume-policy overwrite
```

Run only one post-processing stage when needed:

```bash
uv run main.py --config configs/test.yml --run-id <run_id> --steps splat.cleanup
uv run main.py --config configs/test.yml --run-id <run_id> --steps splat.merge
uv run main.py --config configs/test.yml --run-id <run_id> --steps splat.sog
```

Outputs are written inside the same run directory:

```text
splat/postprocess/postprocess_manifest.json
splat/merged/merged_splat.ply
splat/merged/merged_splat.sog
logs/splat_transform.log
```

Cleanup prefers each patch's `splat_finished.ply`. If a finished file is absent,
the highest-iteration incomplete splat is used with a warning. Missing or failed
cleaned patches are excluded from the merge by default, and the terminal,
warnings log, and post-processing manifest list what was excluded.

The default cleanup settings are scene-relative, not metric. Cleanup and cleaned
PLY merge require wildflow so the old neighbour, area, and boundary filtering
semantics are preserved.

This ordinary patch merge is distinct from future mega-patching, NanoGS, LOD, or
PlayCanvas packaging work.


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

For large reef MCMC runs, build LichtFeld Studio from commit `6d591a34` or later
instead of the `v0.5.2` tag. The `v0.5.2` tag can hit a FastGS bucket-buffer OOM
at full image width even when plenty of VRAM is free; this resembles upstream
allocation issue <https://github.com/MrNeRF/LichtFeld-Studio/issues/1055>. Set
your local `LFS_BIN` in `.env` to the pinned build.

After installing, confirm:

```bash
LichtFeld-Studio --help
LichtFeld-Studio --version
```

### Install wildflow

Install wildflow for cleanup and cleaned PLY merge:

```bash
uv add "wildflow>=0.1.5"
```

After installing, confirm the required splat functions are importable:

```bash
uv run python -c "from wildflow import splat; print(hasattr(splat, 'cleanup_splats'), hasattr(splat, 'merge_ply_files'))"
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
- all temrinal commands seems to print nothing, instead theya ll go to log. at least for patching this is the case, but print out in terminal would be nice too
- Add minimum VRAM guidance + guidance on selecting patch size given img sizes and VRAM. add calculator to figure out what patch size should given gpu vram?
- track vram useage of splat trianing.
- Add more on data collection: link to wildflow guide, state images should be sequential and gaps in data hurt output.
- Add link to download vocab tree.
- Delete or permanently archive old Dataset 1/2 splat comparison outputs in
  `scratch/archived_dataset_runs_20260617_cleanup` once the new patching runs
  have been reviewed.
- Delete or permanently archive the Camera Selection V2 trial run archive in
  `scratch/archived_dataset_runs_20260617T183541Z_camera_selection_v2` once the
  new outputs have been reviewed.
