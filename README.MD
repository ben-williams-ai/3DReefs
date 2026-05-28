# 3DReefs

Tools and workflows for reconstructing large reef areas with photogrammetry and
Gaussian splatting.

## Set up

This project expects a Linux workstation with an NVIDIA GPU. COLMAP is used for
photogrammetry and LichtFeld Studio is used for Gaussian splat training.


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
- Add section on your data
  - Only need 4096 pixels max