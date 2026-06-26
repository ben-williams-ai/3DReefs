#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-3dreefs:local}"
BUILD_JOBS="${BUILD_JOBS:-8}"
CERES_REF="${CERES_REF:-bac1127f9ef672405bd0d2d9c84e809ae89bd239}"
COLMAP_REF="${COLMAP_REF:-5f35f39868de8694913e39a44adcdd8c983504ed}"
CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES:-89;90;100;120}"
LFS_MIN_SM="${LFS_MIN_SM:-89}"

docker build \
  --build-arg BUILD_JOBS="${BUILD_JOBS}" \
  --build-arg CERES_REF="${CERES_REF}" \
  --build-arg COLMAP_REF="${COLMAP_REF}" \
  --build-arg CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES}" \
  --build-arg LFS_MIN_SM="${LFS_MIN_SM}" \
  -t "${IMAGE_NAME}" \
  "${ROOT}"
