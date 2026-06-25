# syntax=docker/dockerfile:1.7
FROM nvidia/cuda:12.8.1-devel-ubuntu24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG COLMAP_VERSION=4.0.4
ARG LFS_REPO=https://github.com/MrNeRF/LichtFeld-Studio.git
ARG LFS_COMMIT=6d591a34
ARG CUDA_ARCHITECTURES="89;90;100;120"
ARG LFS_MIN_SM=89
ARG BUILD_JOBS=8

ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
ENV PATH="/root/.local/bin:/usr/local/cuda/bin:${PATH}"
ENV COLMAP_BIN=/opt/colmap/bin/colmap
ENV LFS_BIN=/opt/lichtfeld-studio/build-release/LichtFeld-Studio
ENV SPLAT_TRANSFORM_BIN=splat-transform
ENV VOCAB_TREE_PATH=/input/vocab_tree.bin
ENV QT_QPA_PLATFORM=offscreen

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cmake \
    curl \
    git \
    gnupg \
    libatlas-base-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-program-options-dev \
    libboost-regex-dev \
    libboost-system-dev \
    libboost-test-dev \
    libcgal-dev \
    libceres-dev \
    libcurl4-openssl-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libgflags-dev \
    libglew-dev \
    libgl1 \
    libgl1-mesa-dev \
    libglvnd-dev \
    libgoogle-glog-dev \
    libmetis-dev \
    libopencv-dev \
    libopenimageio-dev \
    libqt5opengl5-dev \
    libsqlite3-dev \
    libsuitesparse-dev \
    libvulkan-dev \
    libx11-6 \
    libx11-dev \
    libxcb1 \
    libxext-dev \
    ninja-build \
    npm \
    openimageio-tools \
    pkg-config \
    python3 \
    python3-venv \
    qtbase5-dev \
    tar \
    unzip \
    wget \
    zip \
    xz-utils \
  && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN uv tool install cmake

ENV VCPKG_ROOT=/opt/vcpkg
RUN git clone --depth 1 https://github.com/microsoft/vcpkg.git "${VCPKG_ROOT}" \
  && "${VCPKG_ROOT}/bootstrap-vcpkg.sh" -disableMetrics

RUN git clone --depth 1 --branch "${COLMAP_VERSION}" https://github.com/colmap/colmap.git /tmp/colmap \
  && cmake -S /tmp/colmap -B /tmp/colmap/build -GNinja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/opt/colmap \
    -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES}" \
    -DGUI_ENABLED=OFF \
  && cmake --build /tmp/colmap/build --parallel "${BUILD_JOBS}" \
  && cmake --install /tmp/colmap/build \
  && rm -rf /tmp/colmap

RUN --mount=type=cache,target=/opt/vcpkg/downloads \
  --mount=type=cache,target=/opt/vcpkg/buildtrees \
  --mount=type=cache,target=/opt/vcpkg/packages \
  --mount=type=cache,target=/root/.cache/vcpkg \
  git clone --recursive "${LFS_REPO}" /tmp/lichtfeld-studio \
  && cd /tmp/lichtfeld-studio \
  && git checkout "${LFS_COMMIT}" \
  && git submodule update --init --recursive \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
    autoconf \
    autoconf-archive \
    automake \
    g++-14 \
    gcc-14 \
    libegl1-mesa-dev \
    libgtk-3-dev \
    libibus-1.0-dev \
    libdecor-0-dev \
    libdrm-dev \
    libgbm-dev \
    libwayland-dev \
    libx11-dev \
    libxcursor-dev \
    libxext-dev \
    libxfixes-dev \
    libxft-dev \
    libxi-dev \
    libxkbcommon-dev \
    libxrandr-dev \
    libxss-dev \
    libxtst-dev \
    libtool \
    linux-libc-dev \
    nasm \
    wayland-protocols \
  && rm -rf /var/lib/apt/lists/* \
  && if git -C "${VCPKG_ROOT}" rev-parse --is-shallow-repository | grep -q true; then git -C "${VCPKG_ROOT}" fetch --unshallow; fi \
  && cmake -S . -B build-release -GNinja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=/usr/bin/gcc-14 \
    -DCMAKE_CXX_COMPILER=/usr/bin/g++-14 \
    -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/g++-14 \
    -DBUILD_CUDA_PTX_ONLY=ON \
    -DBUILD_CUDA_MIN_SM="${LFS_MIN_SM}" \
    -DLFS_ENFORCE_LINUX_GUI_BACKENDS=OFF \
  && ln -sf /usr/local/cuda/targets/x86_64-linux/lib/stubs/libcuda.so /usr/local/cuda/targets/x86_64-linux/lib/stubs/libcuda.so.1 \
  && LD_LIBRARY_PATH="/usr/local/cuda/targets/x86_64-linux/lib/stubs:${LD_LIBRARY_PATH:-}" cmake --build build-release --parallel "${BUILD_JOBS}" \
  && mkdir -p /opt/lichtfeld-studio \
  && cp -a build-release /opt/lichtfeld-studio/build-release \
  && rm -rf /tmp/lichtfeld-studio

ENV LD_LIBRARY_PATH=/opt/lichtfeld-studio/build-release/Build/lib:/opt/lichtfeld-studio/build-release/vcpkg_installed/x64-linux/lib:/opt/lichtfeld-studio/build-release

RUN npm install -g @playcanvas/splat-transform@1.10.2

ENV REEFS_VENV=/opt/3dreefs-venv

WORKDIR /opt/3dreefs-env
COPY pyproject.toml uv.lock README.MD ./
RUN uv venv "${REEFS_VENV}" \
  && UV_PROJECT_ENVIRONMENT="${REEFS_VENV}" uv sync --frozen --dev

WORKDIR /opt/3DReefs
COPY pyproject.toml uv.lock README.MD ./
COPY src ./src
COPY tests ./tests
COPY configs ./configs
COPY experiments ./experiments
COPY main.py ./main.py

ENTRYPOINT ["/bin/bash", "-lc"]
