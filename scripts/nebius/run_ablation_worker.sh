#!/usr/bin/env bash
set -euo pipefail

BUCKET="${BUCKET:-3dreefs-ben-eu-north1}"
INPUT_PREFIX="${INPUT_PREFIX:-input/datasets}"
OUTPUT_PREFIX="${OUTPUT_PREFIX:-experiments/ablations}"
IMAGE_NAME="${IMAGE_NAME:-cr.eu-north1.nebius.cloud/e00eqkjz0mkvvedmrd/3dreefs:b47af11475c2}"
GIT_REPO="${GIT_REPO:-https://github.com/ben-williams-ai/3DReefs.git}"
GIT_REF="${GIT_REF:-main}"
DATASET_NAME="${DATASET_NAME:?Set DATASET_NAME, e.g. test_dataset}"
RUN_ID="${RUN_ID:-${DATASET_NAME}_$(date -u +%Y%m%dT%H%M%SZ)}"
CONFIG_IN_REPO="${CONFIG_IN_REPO:-configs/docker-test.yml}"
STEPS="${STEPS:-sfm,splat,splat.postprocess}"
RESUME_POLICY="${RESUME_POLICY:-overwrite}"
EXTRA_ARGS="${EXTRA_ARGS:-}"
SCRATCH_ROOT="${SCRATCH_ROOT:-/scratch/3dreefs}"
ENDPOINT_URL="${ENDPOINT_URL:-https://storage.eu-north1.nebius.cloud}"
SHM_SIZE="${SHM_SIZE:-16g}"
PATCH_FILE="${PATCH_FILE:-}"

DATASET_DIR="${SCRATCH_ROOT}/datasets/${DATASET_NAME}"
OUT_ROOT="${SCRATCH_ROOT}/runs/${RUN_ID}"
WORK_DIR="${SCRATCH_ROOT}/worker/${RUN_ID}"
REPO_DIR="${WORK_DIR}/repo"
VOCAB_TREE="${WORK_DIR}/vocab_tree.bin"
EXIT_FILE="${WORK_DIR}/${RUN_ID}.exit"

require_env() {
  if [[ -z "${!1:-}" ]]; then
    echo "Set $1 in the environment." >&2
    exit 2
  fi
}

aws_s3() {
  aws s3 "$@" --endpoint-url "${ENDPOINT_URL}"
}

ensure_aws_cli() {
  if command -v aws >/dev/null 2>&1; then
    return
  fi
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "${tmp_dir}/awscliv2.zip"
  unzip -q "${tmp_dir}/awscliv2.zip" -d "${tmp_dir}"
  sudo "${tmp_dir}/aws/install" --update
  rm -rf "${tmp_dir}"
}

upload_outputs() {
  local code="$1"
  mkdir -p "${WORK_DIR}"
  printf 'EXIT:%s\n' "${code}" > "${EXIT_FILE}"
  if [[ -d "${OUT_ROOT}/project/runs/${RUN_ID}" ]]; then
    aws_s3 sync "${OUT_ROOT}/project/runs/${RUN_ID}" "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/" || true
  fi
  aws_s3 cp "${EXIT_FILE}" "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/${RUN_ID}.exit" || true
}

require_env AWS_ACCESS_KEY_ID
require_env AWS_SECRET_ACCESS_KEY

trap 'code=$?; upload_outputs "${code}"; exit "${code}"' EXIT

sudo apt-get update
sudo apt-get install -y --no-install-recommends ca-certificates curl git unzip zstd
ensure_aws_cli

mkdir -p "${DATASET_DIR}" "${WORK_DIR}" "${OUT_ROOT}"
cd "${WORK_DIR}"

aws_s3 cp "s3://${BUCKET}/${INPUT_PREFIX}/${DATASET_NAME}/raw_images.tar.zst" raw_images.tar.zst
aws_s3 cp "s3://${BUCKET}/${INPUT_PREFIX}/${DATASET_NAME}/raw_images.tar.zst.sha256" raw_images.tar.zst.sha256
expected_hash="$(awk '{print $1; exit}' raw_images.tar.zst.sha256)"
actual_hash="$(sha256sum raw_images.tar.zst | awk '{print $1}')"
if [[ "${expected_hash}" != "${actual_hash}" ]]; then
  echo "Checksum mismatch for ${DATASET_NAME}/raw_images.tar.zst" >&2
  exit 1
fi

rm -rf "${DATASET_DIR}/raw_images"
tar --zstd -xf raw_images.tar.zst -C "${DATASET_DIR}"
test -d "${DATASET_DIR}/raw_images"

rm -rf "${REPO_DIR}"
git clone "${GIT_REPO}" "${REPO_DIR}"
git -C "${REPO_DIR}" checkout "${GIT_REF}"
if [[ -n "${PATCH_FILE}" ]]; then
  git -C "${REPO_DIR}" apply "${PATCH_FILE}"
fi
CONFIG="${REPO_DIR}/${CONFIG_IN_REPO}"
test -f "${CONFIG}"

if [[ -n "${VOCAB_TREE_S3_URI:-}" ]]; then
  aws_s3 cp "${VOCAB_TREE_S3_URI}" "${VOCAB_TREE}"
else
  : > "${VOCAB_TREE}"
fi

docker_args=(
  --rm
  --gpus all
  --shm-size="${SHM_SIZE}" \
  -e HOME="/scratch/3dreefs/home" \
  -e GIT_REPO="${GIT_REPO}" \
  -e GIT_REF="${GIT_REF}" \
  -e RUN_ID="${RUN_ID}" \
  -e STEPS="${STEPS}" \
  -e RESUME_POLICY="${RESUME_POLICY}" \
  -e EXTRA_ARGS="${EXTRA_ARGS}" \
  -v "${DATASET_DIR}:/input/dataset:ro" \
  -v "${DATASET_DIR}/raw_images:/scratch/3dreefs/project/raw_images:ro" \
  -v "${VOCAB_TREE}:/input/vocab_tree.bin:ro" \
  -v "${CONFIG}:/job/config.yml:ro" \
  -v "${OUT_ROOT}:/scratch/3dreefs"
)
if [[ -n "${PATCH_FILE}" ]]; then
  docker_args+=(-v "${PATCH_FILE}:/job/repo.patch:ro")
fi

sudo docker pull "${IMAGE_NAME}"
sudo docker run "${docker_args[@]}" "${IMAGE_NAME}" '
set -euo pipefail

mkdir -p "${HOME}" /scratch/3dreefs/code /scratch/3dreefs/project
rm -rf /scratch/3dreefs/code/3DReefs
git clone "${GIT_REPO}" /scratch/3dreefs/code/3DReefs
cd /scratch/3dreefs/code/3DReefs
git checkout "${GIT_REF}"
if [[ -f /job/repo.patch ]]; then
  git apply /job/repo.patch
fi
COMMIT="$(git rev-parse HEAD)"

cat > /scratch/3dreefs/git_checkout.env <<EOF
GIT_REPO=${GIT_REPO}
GIT_REF=${GIT_REF}
GIT_COMMIT=${COMMIT}
EOF

mkdir -p "/scratch/3dreefs/project/runs/${RUN_ID}"
read -r -a extra_args <<< "${EXTRA_ARGS}"

"${REEFS_VENV}/bin/python" main.py \
  --config /job/config.yml \
  --steps "${STEPS}" \
  --resume-policy "${RESUME_POLICY}" \
  --run-id "${RUN_ID}" \
  "${extra_args[@]}"
'
