#!/usr/bin/env bash
set -euo pipefail

: "${DATASET_NAME:?Set DATASET_NAME, e.g. dataset2}"
: "${SOURCE_BUNDLE_URI:?Set SOURCE_BUNDLE_URI to a verified Stage 2 source prefix}"
: "${TRAINING_RESOLUTION:?Set TRAINING_RESOLUTION to 1024, 2048, or full}"
: "${PATCH_SIZE:?Set PATCH_SIZE to 200, 400, or 800}"
: "${SPLAT_COUNTS:?Set SPLAT_COUNTS, e.g. 500000,1000000,2000000}"

export SOURCE_VARIANT="${SOURCE_VARIANT:-sfm_1024_sift_global}"
[[ "${SOURCE_VARIANT}" == "sfm_1024_sift_global" ]] || { echo "Unsupported source variant." >&2; exit 2; }
[[ "${TRAINING_RESOLUTION}" =~ ^(1024|2048|full)$ ]] || { echo "Invalid training resolution." >&2; exit 2; }
[[ "${PATCH_SIZE}" =~ ^(200|400|800)$ ]] || { echo "Invalid patch size." >&2; exit 2; }
[[ "${SPLAT_COUNTS}" =~ ^(500000|1000000|2000000)(,(500000|1000000|2000000))*$ ]] || {
  echo "Invalid splat counts." >&2
  exit 2
}

export SUBNET_ID="${SUBNET_ID:-vpcsubnet-e00csjbw2tzwzxe41m}"
export BUCKET="${BUCKET:-3dreefs-ben-eu-north1}"
export OUTPUT_PREFIX="${OUTPUT_PREFIX:-experiments/ablations/stage2_resolution_fullres_eval}"
export IMAGE_NAME="${IMAGE_NAME:-cr.eu-north1.nebius.cloud/e00eqkjz0mkvvedmrd/3dreefs:colmap404-python-eval-20260707}"
export IMAGE_DIGEST="${IMAGE_DIGEST:-sha256:49b16c6f885144bd7517f37c28194b013a78e7b73739183579ac09a6ebce9006}"
export JOB_ID="${JOB_ID:-splat_${DATASET_NAME}_${SOURCE_VARIANT}_res${TRAINING_RESOLUTION}_patch${PATCH_SIZE}_stage2}"
export RUN_ID="${RUN_ID:-${JOB_ID}}"
export GIT_REPO="${GIT_REPO:-https://github.com/ben-williams-ai/3DReefs.git}"
export GIT_REF="${GIT_REF:-$(git rev-parse origin/main)}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-$(aws configure get aws_access_key_id)}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-$(aws configure get aws_secret_access_key)}"
export BOOT_DISK_GIB="${BOOT_DISK_GIB:-960}"
export DELETE_ON_FINISH="${DELETE_ON_FINISH:-true}"
export WORKER_MODE="stage2_splat_eval"

case "${DATASET_NAME}" in
  dataset1) export CONFIG_IN_REPO="configs/datasets/dataset_01.yml" ;;
  dataset2) export CONFIG_IN_REPO="configs/datasets/dataset_02.yml" ;;
  dataset3) export CONFIG_IN_REPO="configs/datasets/dataset_03.yml" ;;
  dataset4) export CONFIG_IN_REPO="configs/datasets/dataset_04.yml" ;;
  dataset5) export CONFIG_IN_REPO="configs/datasets/dataset_05.yml" ;;
  *) echo "Unsupported Stage 2 dataset: ${DATASET_NAME}" >&2; exit 2 ;;
esac

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
if aws s3 ls "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/" \
  --endpoint-url "${ENDPOINT_URL:-https://storage.eu-north1.nebius.cloud}" | grep -q .; then
  echo "Refusing to reuse non-empty Stage 2 result prefix for ${RUN_ID}." >&2
  exit 2
fi

IFS=',' read -r -a counts <<< "${SPLAT_COUNTS}"
printf 'Stage 2 batch: dataset=%s resolution=%s patch=%s source=%s\n' \
  "${DATASET_NAME}" "${TRAINING_RESOLUTION}" "${PATCH_SIZE}" "${SOURCE_BUNDLE_URI}"
for count in "${counts[@]}"; do
  if (( count % 1000000 == 0 )); then suffix="$((count / 1000000))m"; else suffix="$((count / 1000))k"; fi
  printf '  probe=%s\n' "splat_${DATASET_NAME}_${SOURCE_VARIANT}_res${TRAINING_RESOLUTION}_patch${PATCH_SIZE}_${suffix}"
done
scripts/nebius/launch_worker_vm.sh
