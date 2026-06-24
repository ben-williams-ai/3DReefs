#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-3dreefs:local}"
BUILD_JOBS="${BUILD_JOBS:-8}"
CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES:-89;90;100;120}"
LFS_MIN_SM="${LFS_MIN_SM:-89}"

docker build \
  --build-arg BUILD_JOBS="${BUILD_JOBS}" \
  --build-arg CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES}" \
  --build-arg LFS_MIN_SM="${LFS_MIN_SM}" \
  -t "${IMAGE_NAME}" \
  "${ROOT}"
