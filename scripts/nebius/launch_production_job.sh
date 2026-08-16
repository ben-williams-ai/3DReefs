#!/usr/bin/env bash
set -euo pipefail

: "${DATASET_NAME:?Set DATASET_NAME to dataset1 through dataset6}"
[[ "${DATASET_NAME}" =~ ^dataset[1-6]$ ]] || {
  echo "DATASET_NAME must be dataset1 through dataset6." >&2
  exit 2
}

dataset_number="${DATASET_NAME#dataset}"
if [[ "${dataset_number}" == "1" ]]; then
  profile="configs/colour-profiles/dataset1-colour.json"
else
  profile="configs/colour-profiles/dataset_0${dataset_number}-colour.json"
fi

export SUBNET_ID="${SUBNET_ID:-vpcsubnet-e00csjbw2tzwzxe41m}"
export BUCKET="${BUCKET:-3dreefs-ben-eu-north1}"
export OUTPUT_PREFIX="${OUTPUT_PREFIX:-experiments/production/colour_corrected_full_models/v1}"
export RUN_ID="${RUN_ID:-colour_corrected_full_dataset${dataset_number}_v1}"
export JOB_ID="${JOB_ID:-${RUN_ID}}"
export VM_NAME="${VM_NAME:-${RUN_ID}}"
export SOURCE_VARIANT="sfm_1024_sift_global"
export SOURCE_BUNDLE_URI="${SOURCE_BUNDLE_URI:-s3://${BUCKET}/experiments/ablations/stage2_sources/runs/sfm_${DATASET_NAME}_${SOURCE_VARIANT}_stage2_source}"
export IMAGE_NAME="${IMAGE_NAME:-cr.eu-north1.nebius.cloud/e00eqkjz0mkvvedmrd/3dreefs:colmap404-python-eval-20260722-metadata-recovery}"
export IMAGE_DIGEST="${IMAGE_DIGEST:-sha256:dd415e4e6d2775648e088f264ecd08997decc591ee399d4183497e2dabbe6af8}"
export GIT_REPO="${GIT_REPO:-https://github.com/ben-williams-ai/3DReefs.git}"
export GIT_REF="${GIT_REF:-$(git rev-parse origin/main)}"
export CONFIG_IN_REPO="configs/datasets/dataset_0${dataset_number}.yml"
export COLOUR_PROFILE_SHA256="$(sha256sum "${profile}" | awk '{print $1}')"
export WORKER_MODE="production"
export WORKER_SCRIPT="scripts/nebius/run_worker.sh"
export PRODUCTION_CANARY="${PRODUCTION_CANARY:-false}"
export BOOT_DISK_GIB="${BOOT_DISK_GIB:-960}"
export DELETE_ON_FINISH="${DELETE_ON_FINISH:-true}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-$(aws configure get aws_access_key_id)}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-$(aws configure get aws_secret_access_key)}"

git merge-base --is-ancestor "${GIT_REF}" origin/main || {
  echo "GIT_REF is not present on pushed origin/main: ${GIT_REF}" >&2
  exit 2
}
actual_digest="$(docker buildx imagetools inspect "${IMAGE_NAME}" | awk '/^Digest:/ {print $2; exit}')"
[[ "${actual_digest}" == "${IMAGE_DIGEST}" ]] || {
  echo "Container digest mismatch: ${actual_digest:-missing} != ${IMAGE_DIGEST}" >&2
  exit 2
}
source_complete="$(aws s3 cp "${SOURCE_BUNDLE_URI%/}/source_complete.json" - --no-progress \
  --endpoint-url "${ENDPOINT_URL:-https://storage.eu-north1.nebius.cloud}")"
SOURCE_COMPLETE="${source_complete}" python3 -c '
import json
import os
payload = json.loads(os.environ["SOURCE_COMPLETE"])
if payload.get("status") != "verified_complete" or payload.get("upload_status") != 0:
    raise SystemExit("source bundle is not verified complete")
'
if aws s3 ls "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/" --recursive \
  --endpoint-url "${ENDPOINT_URL:-https://storage.eu-north1.nebius.cloud}" | grep -q .; then
  echo "Refusing to reuse non-empty production prefix for ${RUN_ID}." >&2
  exit 2
fi

printf 'Production run: dataset=%s run=%s source=%s canary=%s\n' \
  "${DATASET_NAME}" "${RUN_ID}" "${SOURCE_BUNDLE_URI}" "${PRODUCTION_CANARY}"
scripts/nebius/launch_worker_vm.sh
