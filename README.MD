# 3DReefs

Tools and workflows for reconstructing large reef areas with photogrammetry and
Gaussian splatting.

## Set up

This project expects a Linux workstation with an NVIDIA GPU. COLMAP is used for
photogrammetry and LichtFeld Studio is used for Gaussian splat training.

Install the Python project environment with `uv`:

```bash
uv sync
```


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

These were the latest stable releases available when this setup was written. Newer versions may work, but command-line options and build requirements can
change.

- COLMAP `4.0.4`
- LichtFeld Studio `v0.5.2`

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
uv run main.py --config configs/example.yml --steps sfm,splat --resume-policy resume
```

The public config layout keeps mandatory `project` and `tools` sections first;
all other settings live under `advanced`. Normal paths are derived from `project.dir`: `raw_images/`, optional
`recoloured_images/`, and `runs/`. Public example configs use placeholders; make
local copies for machine-specific paths.

Each foundation run writes records under `<project.dir>/runs/<run_id>/`:

```text
effective_config.yml
cli_overrides.json
run_manifest.json
run_status.json
timings.json
logs/pipeline.log
logs/warnings.log
reports/preflight_report.md
```

If prior partial outputs are detected, resume/overwrite decisions are gathered
during preflight before any requested step starts. Non-interactive runs must use
an explicit `--resume-policy`.


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

### Install LichtFeld Studio

Follow the official Linux build instructions:

- <https://github.com/MrNeRF/LichtFeld-Studio/wiki/Build-Instructions-%E2%80%90-Linux>

After installing, confirm:

```bash
LichtFeld-Studio --help
LichtFeld-Studio --version
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
- Add minimum VRAM guidance.
