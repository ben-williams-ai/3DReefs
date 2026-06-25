#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-3dreefs:local}"
TEST_DATASET="${TEST_DATASET:-${ROOT}/data/test_dataset}"
VOCAB_TREE="${VOCAB_TREE:-}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="${RUN_ID:-docker_test_${STAMP}}"
OUT_ROOT="${OUT_ROOT:-${ROOT}/scratch/docker-e2e/${STAMP}}"

if [[ -z "${VOCAB_TREE}" ]]; then
  echo "Set VOCAB_TREE to a local vocab-tree .bin path." >&2
  exit 2
fi
if [[ ! -d "${TEST_DATASET}" ]]; then
  echo "Test dataset not found: ${TEST_DATASET}" >&2
  exit 2
fi
if [[ ! -f "${VOCAB_TREE}" ]]; then
  echo "Vocab tree not found: ${VOCAB_TREE}" >&2
  exit 2
fi

mkdir -p "${OUT_ROOT}/project"

docker run --rm --gpus all \
  --shm-size=16g \
  -e RUN_ID="${RUN_ID}" \
  -e LD_LIBRARY_PATH="/opt/lichtfeld-studio/build-release/Build/lib:/opt/lichtfeld-studio/build-release/vcpkg_installed/x64-linux/lib:/opt/lichtfeld-studio/build-release" \
  -v "${TEST_DATASET}:/input/test_dataset:ro" \
  -v "${VOCAB_TREE}:/input/vocab_tree.bin:ro" \
  -v "${OUT_ROOT}:/scratch/3dreefs" \
  "${IMAGE_NAME}" '
set -euo pipefail
rm -rf /scratch/3dreefs/project/raw_images
ln -s /input/test_dataset/raw_images /scratch/3dreefs/project/raw_images
mkdir -p "/scratch/3dreefs/project/runs/${RUN_ID}"
uv run pytest tests/unit/test_ablation_grid.py tests/unit/test_ablation_ledger.py tests/unit/test_ablation_runner.py
uv run main.py \
  --config configs/docker-test.yml \
  --steps sfm,splat,splat.postprocess \
  --resume-policy overwrite \
  --run-id "${RUN_ID}"
test -f "/scratch/3dreefs/project/runs/${RUN_ID}/run_status.json"
find "/scratch/3dreefs/project/runs/${RUN_ID}/splat" -type f \( -name "*.ply" -o -name "*.sog" \) -print -quit | grep .
'

echo "Docker E2E output: ${OUT_ROOT}/project/runs/${RUN_ID}"
