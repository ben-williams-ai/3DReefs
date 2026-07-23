#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-3dreefs:local}"
BUILD_JOBS="${BUILD_JOBS:-8}"
CERES_REF="${CERES_REF:-bac1127f9ef672405bd0d2d9c84e809ae89bd239}"
COLMAP_REF="${COLMAP_REF:-9c23f6942fe69962e06030905e77067c8673382f}"
CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES:-89;90;100;120}"
LFS_MIN_SM="${LFS_MIN_SM:-89}"
GIT_COMMIT="${GIT_COMMIT:-$(git -C "${ROOT}" rev-parse HEAD)}"

docker build \
  --build-arg BUILD_JOBS="${BUILD_JOBS}" \
  --build-arg CERES_REF="${CERES_REF}" \
  --build-arg COLMAP_REF="${COLMAP_REF}" \
  --build-arg CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES}" \
  --build-arg LFS_MIN_SM="${LFS_MIN_SM}" \
  --build-arg GIT_COMMIT="${GIT_COMMIT}" \
  -t "${IMAGE_NAME}" \
  "${ROOT}"
