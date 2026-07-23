# syntax=docker/dockerfile:1.7
FROM nvidia/cuda:12.8.1-devel-ubuntu24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG CERES_REF=bac1127f9ef672405bd0d2d9c84e809ae89bd239
ARG COLMAP_REF=9c23f6942fe69962e06030905e77067c8673382f
ARG LFS_REPO=https://github.com/MrNeRF/LichtFeld-Studio.git
ARG LFS_COMMIT=6d591a34
ARG CUDA_ARCHITECTURES="89;90;100;120"
ARG LFS_MIN_SM=89
ARG BUILD_JOBS=8
ARG GIT_COMMIT=unknown

LABEL org.opencontainers.image.revision="${GIT_COMMIT}"

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
    libcudss0-dev-cuda-12 \
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
    mesa-vulkan-drivers \
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

ENV CUDSS_DIR=/usr/lib/x86_64-linux-gnu/libcudss/12/cmake/cudss
ENV CUDSS_LIB_DIR=/usr/lib/x86_64-linux-gnu/libcudss/12

RUN for header in /usr/include/libcudss/12/*.h; do ln -sf "${header}" "/usr/include/$(basename "${header}")"; done \
  && if [ -f "${CUDSS_DIR}/cudss-static-targets.cmake" ] && [ ! -f "${CUDSS_LIB_DIR}/libcudss_static.a" ]; then \
      mv "${CUDSS_DIR}/cudss-static-targets.cmake" "${CUDSS_DIR}/cudss-static-targets.cmake.disabled"; \
    fi \
  && if [ -f "${CUDSS_DIR}/cudss-static-targets-release.cmake" ] && [ ! -f "${CUDSS_LIB_DIR}/libcudss_static.a" ]; then \
      mv "${CUDSS_DIR}/cudss-static-targets-release.cmake" "${CUDSS_DIR}/cudss-static-targets-release.cmake.disabled"; \
    fi

RUN git clone --recurse-submodules https://github.com/ceres-solver/ceres-solver.git /tmp/ceres-solver \
  && cd /tmp/ceres-solver \
  && git checkout "${CERES_REF}" \
  && git submodule update --init --recursive \
  && cmake -S /tmp/ceres-solver -B /tmp/ceres-solver/build -GNinja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/opt/colmap \
    -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES}" \
    -DBUILD_SHARED_LIBS=ON \
    -DBUILD_TESTING=OFF \
    -DBUILD_EXAMPLES=OFF \
    -DBUILD_BENCHMARKS=OFF \
    -DUSE_CUDA=ON \
    -DEIGENSPARSE=ON \
    -DSUITESPARSE=ON \
    -DLAPACK=ON \
    -Dcudss_DIR="${CUDSS_DIR}" \
  && if grep -Eq "^[[:space:]]*#define[[:space:]]+CERES_NO_CUDSS" /tmp/ceres-solver/build/include/ceres/internal/config.h; then \
      echo "Ceres configured without cuDSS" >&2; exit 1; \
    fi \
  && cmake --build /tmp/ceres-solver/build --parallel "${BUILD_JOBS}" \
  && cmake --install /tmp/ceres-solver/build \
  && rm -rf /tmp/ceres-solver

RUN git clone https://github.com/colmap/colmap.git /tmp/colmap \
  && cd /tmp/colmap \
  && git checkout "${COLMAP_REF}" \
  && cmake -S /tmp/colmap -B /tmp/colmap/build -GNinja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/opt/colmap \
    -DCMAKE_PREFIX_PATH="/opt/colmap;${CUDSS_LIB_DIR}" \
    -Dcudss_DIR="${CUDSS_DIR}" \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES}" \
    -DGUI_ENABLED=OFF \
  && cmake --build /tmp/colmap/build --parallel "${BUILD_JOBS}" \
  && cmake --install /tmp/colmap/build \
  && ln -sf "${CUDSS_LIB_DIR}"/libcudss*.so* /opt/colmap/lib/ \
  && ceres_path="$(ldd /opt/colmap/bin/colmap | awk '/libceres/{print $3; exit}')" \
  && ceres_real="$(readlink -f "${ceres_path}")" \
  && echo "COLMAP Ceres: ${ceres_real}" \
  && case "${ceres_real}" in /opt/colmap/lib/*) ;; *) echo "COLMAP is not linked to /opt/colmap Ceres" >&2; exit 1 ;; esac \
  && (ldd /opt/colmap/bin/colmap | grep -qi cudss || strings /opt/colmap/bin/colmap | grep -qi cudss) \
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
  && cp -a eval /opt/lichtfeld-studio/eval \
  && rm -rf /tmp/lichtfeld-studio

ENV LD_LIBRARY_PATH=/opt/colmap/lib:/usr/lib/x86_64-linux-gnu/libcudss/12:/opt/lichtfeld-studio/build-release/Build/lib:/opt/lichtfeld-studio/build-release/vcpkg_installed/x64-linux/lib:/opt/lichtfeld-studio/build-release

RUN mkdir -p /opt/colmap/models \
  && curl -LfsS -o /opt/colmap/models/aliked-n16rot.onnx \
    https://github.com/colmap/colmap/releases/download/3.13.0/aliked-n16rot.onnx \
  && echo "39c423d0a6f03d39ec89d3d1d61853765c2fb6a8b8381376c703e5758778a547  /opt/colmap/models/aliked-n16rot.onnx" | sha256sum -c - \
  && curl -LfsS -o /opt/colmap/models/aliked-n32.onnx \
    https://github.com/colmap/colmap/releases/download/3.13.0/aliked-n32.onnx \
  && echo "a077728a02d2de1a775c66df6de8cfeb7c6b51ca57572c64c680131c988c8b3c  /opt/colmap/models/aliked-n32.onnx" | sha256sum -c - \
  && curl -LfsS -o /opt/colmap/models/aliked-bruteforce-matcher.onnx \
    https://github.com/colmap/colmap/releases/download/3.13.0/bruteforce-matcher.onnx \
  && echo "3c1282f96d83f5ffc861a873298d08bbe5219f59af59223f5ceab5c41a182a47  /opt/colmap/models/aliked-bruteforce-matcher.onnx" | sha256sum -c -

ENV ALIKED_N16ROT_MODEL_PATH=/opt/colmap/models/aliked-n16rot.onnx
ENV ALIKED_N32_MODEL_PATH=/opt/colmap/models/aliked-n32.onnx
ENV ALIKED_BRUTEFORCE_MATCHER_MODEL_PATH=/opt/colmap/models/aliked-bruteforce-matcher.onnx

RUN npm install -g @playcanvas/splat-transform@1.10.2

RUN apt-get update \
  && apt-get install -y --no-install-recommends libimage-exiftool-perl \
  && rm -rf /var/lib/apt/lists/*

ENV REEFS_VENV=/opt/3dreefs-venv

WORKDIR /opt/3dreefs-env
COPY pyproject.toml uv.lock README.MD ./
RUN uv venv "${REEFS_VENV}" \
  && UV_PROJECT_ENVIRONMENT="${REEFS_VENV}" uv sync --frozen --dev

COPY src /opt/3dreefs-source/src
COPY scripts /opt/3dreefs-source/scripts
COPY experiments/ablations /opt/3dreefs-source/experiments/ablations

ENV LD_LIBRARY_PATH=/opt/colmap/lib:/usr/lib/x86_64-linux-gnu/libcudss/12:/opt/lichtfeld-studio/build-release/Build/lib:/opt/lichtfeld-studio/build-release/vcpkg_installed/x64-linux/lib:/opt/lichtfeld-studio/build-release:/opt/3dreefs-venv/lib/python3.12/site-packages/nvidia/cu13/lib:/opt/3dreefs-venv/lib/python3.12/site-packages/nvidia/cudnn/lib:/opt/3dreefs-venv/lib/python3.12/site-packages/nvidia/cusparselt/lib:/opt/3dreefs-venv/lib/python3.12/site-packages/nvidia/nccl/lib:/opt/3dreefs-venv/lib/python3.12/site-packages/nvidia/nvshmem/lib

WORKDIR /opt/3DReefs
COPY pyproject.toml uv.lock README.MD ./
COPY src ./src
COPY tests ./tests
COPY configs ./configs
COPY experiments ./experiments
COPY main.py ./main.py

ENTRYPOINT ["/bin/bash", "-lc"]
