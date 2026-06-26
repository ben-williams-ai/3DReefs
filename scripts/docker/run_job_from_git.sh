#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-3dreefs:local}"
GIT_REPO="${GIT_REPO:-https://github.com/ben-williams-ai/3DReefs.git}"
GIT_REF="${GIT_REF:-main}"
STEPS="${STEPS:-sfm,splat,splat.postprocess}"
RESUME_POLICY="${RESUME_POLICY:-overwrite}"
SHM_SIZE="${SHM_SIZE:-16g}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="${RUN_ID:-job_${STAMP}}"
DATASET="${DATASET:-}"
VOCAB_TREE="${VOCAB_TREE:-}"
CONFIG="${CONFIG:-}"
OUT_ROOT="${OUT_ROOT:-}"

if [[ -z "${DATASET}" || ! -d "${DATASET}" ]]; then
  echo "Set DATASET to a local dataset directory." >&2
  exit 2
fi
if [[ ! -d "${DATASET}/raw_images" ]]; then
  echo "Dataset must contain raw_images/: ${DATASET}" >&2
  exit 2
fi
if [[ -z "${VOCAB_TREE}" || ! -f "${VOCAB_TREE}" ]]; then
  echo "Set VOCAB_TREE to a local vocab-tree .bin file." >&2
  exit 2
fi
if [[ -z "${CONFIG}" || ! -f "${CONFIG}" ]]; then
  echo "Set CONFIG to a local config YAML file." >&2
  exit 2
fi
if [[ -z "${OUT_ROOT}" ]]; then
  echo "Set OUT_ROOT to a writable output directory." >&2
  exit 2
fi

mkdir -p "${OUT_ROOT}"

docker run --rm --gpus all \
  --user "$(id -u):$(id -g)" \
  --shm-size="${SHM_SIZE}" \
  -e HOME="/scratch/3dreefs/home" \
  -e GIT_REPO="${GIT_REPO}" \
  -e GIT_REF="${GIT_REF}" \
  -e RUN_ID="${RUN_ID}" \
  -e STEPS="${STEPS}" \
  -e RESUME_POLICY="${RESUME_POLICY}" \
  -v "${DATASET}:/input/dataset:ro" \
  -v "${VOCAB_TREE}:/input/vocab_tree.bin:ro" \
  -v "${CONFIG}:/job/config.yml:ro" \
  -v "${OUT_ROOT}:/scratch/3dreefs" \
  "${IMAGE_NAME}" '
set -euo pipefail

mkdir -p "${HOME}" /scratch/3dreefs/code /scratch/3dreefs/project
rm -rf /scratch/3dreefs/code/3DReefs
git clone "${GIT_REPO}" /scratch/3dreefs/code/3DReefs
cd /scratch/3dreefs/code/3DReefs
git checkout "${GIT_REF}"
COMMIT="$(git rev-parse HEAD)"

cat > /scratch/3dreefs/git_checkout.env <<EOF
GIT_REPO=${GIT_REPO}
GIT_REF=${GIT_REF}
GIT_COMMIT=${COMMIT}
EOF

if [[ -f uv.lock ]] && ! cmp -s /opt/3dreefs-env/uv.lock uv.lock; then
  echo "Warning: cloned uv.lock differs from the image uv.lock; rebuild the image if dependencies changed." >&2
fi

rm -rf /scratch/3dreefs/project/raw_images
ln -s /input/dataset/raw_images /scratch/3dreefs/project/raw_images
mkdir -p "/scratch/3dreefs/project/runs/${RUN_ID}"

"${REEFS_VENV}/bin/python" main.py \
  --config /job/config.yml \
  --steps "${STEPS}" \
  --resume-policy "${RESUME_POLICY}" \
  --run-id "${RUN_ID}"
'

echo "Docker Git job output: ${OUT_ROOT}/project/runs/${RUN_ID}"
