#!/usr/bin/env bash
set -euo pipefail

: "${DATASET_NAME:?Set DATASET_NAME, e.g. dataset3}"
: "${STAGE1_VARIANT:?Set STAGE1_VARIANT, e.g. sfm_baseline}"

export SUBNET_ID="${SUBNET_ID:-vpcsubnet-e00csjbw2tzwzxe41m}"
export BUCKET="${BUCKET:-3dreefs-ben-eu-north1}"
export OUTPUT_PREFIX="${OUTPUT_PREFIX:-experiments/ablations/stage1_fullres_eval}"
export IMAGE_NAME="${IMAGE_NAME:-cr.eu-north1.nebius.cloud/e00eqkjz0mkvvedmrd/3dreefs:colmap404-python-eval-20260722-metadata-recovery}"
export IMAGE_DIGEST="${IMAGE_DIGEST:-sha256:dd415e4e6d2775648e088f264ecd08997decc591ee399d4183497e2dabbe6af8}"
export JOB_ID="${JOB_ID:-sfm_${DATASET_NAME}_${STAGE1_VARIANT}}"
export RUN_ID="${RUN_ID:-$JOB_ID}"
export GIT_REPO="${GIT_REPO:-https://github.com/ben-williams-ai/3DReefs.git}"
export GIT_REF="${GIT_REF:-$(git rev-parse origin/main)}"
export VOCAB_TREE_S3_URI="${VOCAB_TREE_S3_URI:-s3://3dreefs-ben-eu-north1/input/assets/vocab_tree_faiss_flickr100K_words256K.bin}"
export ALIKED_N16ROT_VOCAB_TREE_S3_URI="${ALIKED_N16ROT_VOCAB_TREE_S3_URI:-s3://3dreefs-ben-eu-north1/input/assets/vocab_tree_faiss_flickr100K_words64K_aliked_n16rot.bin}"
export ALIKED_N32_VOCAB_TREE_S3_URI="${ALIKED_N32_VOCAB_TREE_S3_URI:-s3://3dreefs-ben-eu-north1/input/assets/vocab_tree_faiss_flickr100K_words64K_aliked_n32.bin}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-$(aws configure get aws_access_key_id)}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-$(aws configure get aws_secret_access_key)}"
export DELETE_ON_FINISH="${DELETE_ON_FINISH:-true}"
export WORKER_MODE="stage1_sfm_eval"

case "${DATASET_NAME}" in
  dataset1) export CONFIG_IN_REPO="configs/datasets/dataset_01.yml" ;;
  dataset2) export CONFIG_IN_REPO="configs/datasets/dataset_02.yml" ;;
  dataset3) export CONFIG_IN_REPO="configs/datasets/dataset_03.yml" ;;
  dataset4) export CONFIG_IN_REPO="configs/datasets/dataset_04.yml" ;;
  dataset5) export CONFIG_IN_REPO="configs/datasets/dataset_05.yml" ;;
  dataset6) export CONFIG_IN_REPO="configs/datasets/dataset_06.yml" ;;
  dataset7) export CONFIG_IN_REPO="configs/datasets/dataset_07.yml" ;;
  *) echo "Unsupported Stage 1 Nebius dataset: ${DATASET_NAME}" >&2; exit 2 ;;
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

scripts/nebius/launch_worker_vm.sh
