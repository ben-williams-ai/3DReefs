#!/usr/bin/env bash
set -euo pipefail

: "${DATASET_NAME:?Set DATASET_NAME, e.g. dataset3}"
: "${STAGE1_VARIANT:?Set STAGE1_VARIANT, e.g. sfm_baseline}"

export SUBNET_ID="${SUBNET_ID:-vpcsubnet-e00csjbw2tzwzxe41m}"
export BUCKET="${BUCKET:-3dreefs-ben-eu-north1}"
export OUTPUT_PREFIX="${OUTPUT_PREFIX:-experiments/ablations/stage1}"
export IMAGE_NAME="${IMAGE_NAME:-cr.eu-north1.nebius.cloud/e00eqkjz0mkvvedmrd/3dreefs:c708a13}"
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
  dataset3) export CONFIG_IN_REPO="configs/datasets/dataset_03.yml" ;;
  dataset4) export CONFIG_IN_REPO="configs/datasets/dataset_04.yml" ;;
  *) echo "Unsupported Stage 1 Nebius dataset: ${DATASET_NAME}" >&2; exit 2 ;;
esac

scripts/nebius/launch_worker_vm.sh
