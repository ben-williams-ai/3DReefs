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
EVAL_PATCH_COUNT="${EVAL_PATCH_COUNT:-}"
EVAL_VARIANT="${EVAL_VARIANT:-scratch_eval}"
RESUME_FROM_S3_URI="${RESUME_FROM_S3_URI:-}"
WORKER_MODE="${WORKER_MODE:-pipeline}"
STAGE1_VARIANT="${STAGE1_VARIANT:-}"

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
  if [[ -d "${OUT_ROOT}/project/ablation_eval" ]]; then
    aws_s3 sync "${OUT_ROOT}/project/ablation_eval" "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/ablation_eval/" || true
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

if [[ -n "${RESUME_FROM_S3_URI}" ]]; then
  mkdir -p "${OUT_ROOT}/project/runs/${RUN_ID}"
  aws_s3 sync "${RESUME_FROM_S3_URI%/}/" "${OUT_ROOT}/project/runs/${RUN_ID}/"
fi

if [[ "${GIT_REPO}" != "IMAGE" ]]; then
  rm -rf "${REPO_DIR}"
  git clone "${GIT_REPO}" "${REPO_DIR}"
  git -C "${REPO_DIR}" checkout "${GIT_REF}"
  if [[ -n "${PATCH_FILE}" ]]; then
    git -C "${REPO_DIR}" apply "${PATCH_FILE}"
  fi
  CONFIG="${REPO_DIR}/${CONFIG_IN_REPO}"
  test -f "${CONFIG}"
else
  CONFIG=""
fi

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
  -e CONFIG_IN_REPO="${CONFIG_IN_REPO}" \
  -e DATASET_NAME="${DATASET_NAME}" \
  -e RUN_ID="${RUN_ID}" \
  -e STEPS="${STEPS}" \
  -e RESUME_POLICY="${RESUME_POLICY}" \
  -e EXTRA_ARGS="${EXTRA_ARGS}" \
  -e EVAL_PATCH_COUNT="${EVAL_PATCH_COUNT}" \
  -e EVAL_VARIANT="${EVAL_VARIANT}" \
  -e WORKER_MODE="${WORKER_MODE}" \
  -e STAGE1_VARIANT="${STAGE1_VARIANT}" \
  -e RESUME_FROM_S3_URI="${RESUME_FROM_S3_URI}" \
  -v "${DATASET_DIR}:/input/dataset:ro" \
  -v "${DATASET_DIR}/raw_images:/scratch/3dreefs/project/raw_images:ro" \
  -v "${VOCAB_TREE}:/input/vocab_tree.bin:ro" \
  -v "${OUT_ROOT}:/scratch/3dreefs"
)
if [[ -n "${CONFIG}" ]]; then
  docker_args+=(-v "${CONFIG}:/job/config.yml:ro")
fi
if [[ -n "${PATCH_FILE}" ]]; then
  docker_args+=(-v "${PATCH_FILE}:/job/repo.patch:ro")
fi

sudo docker pull "${IMAGE_NAME}"
sudo docker run "${docker_args[@]}" "${IMAGE_NAME}" '
set -euo pipefail

mkdir -p "${HOME}" /scratch/3dreefs/code /scratch/3dreefs/project
if [[ "${GIT_REPO}" == "IMAGE" ]]; then
  cd /opt/3DReefs
  COMMIT="${GIT_REF}"
else
  rm -rf /scratch/3dreefs/code/3DReefs
  git clone "${GIT_REPO}" /scratch/3dreefs/code/3DReefs
  cd /scratch/3dreefs/code/3DReefs
  git checkout "${GIT_REF}"
  if [[ -f /job/repo.patch ]]; then
    git apply /job/repo.patch
  fi
  COMMIT="$(git rev-parse HEAD)"
fi
export PYTHONPATH="${PWD}/src${PYTHONPATH:+:${PYTHONPATH}}"
CONFIG_PATH="/job/config.yml"
if [[ ! -f "${CONFIG_PATH}" ]]; then
  CONFIG_PATH="/opt/3DReefs/${CONFIG_IN_REPO}"
fi

cat > /scratch/3dreefs/git_checkout.env <<EOF
GIT_REPO=${GIT_REPO}
GIT_REF=${GIT_REF}
GIT_COMMIT=${COMMIT}
EOF

mkdir -p "/scratch/3dreefs/project/runs/${RUN_ID}"
read -r -a extra_args <<< "${EXTRA_ARGS}"

run_pipeline() {
  local steps="$1"
  local resume_policy="$2"
  shift 2
  "${REEFS_VENV}/bin/python" main.py \
    --config "${CONFIG_PATH}" \
    --project-dir /scratch/3dreefs/project \
    --steps "${steps}" \
    --resume-policy "${resume_policy}" \
    --run-id "${RUN_ID}" \
    "${extra_args[@]}" \
    "$@"
}

write_eval_summary() {
  local patch_list="$1"
  "${REEFS_VENV}/bin/python" - "${RUN_ID}" "${EVAL_VARIANT}" "${patch_list}" <<'"'"'PY'"'"'
import csv
import json
import sys
from pathlib import Path

run_id, variant, patch_list = sys.argv[1:4]
run_dir = Path("/scratch/3dreefs/project/runs") / run_id
patch_ids = [item for item in patch_list.strip("[]").split(",") if item]
summary_dir = run_dir / "ablation_eval"
summary_dir.mkdir(parents=True, exist_ok=True)

rows = []
for patch_id in patch_ids:
    patch_dir = run_dir / "splat" / "patches" / patch_id
    status_path = patch_dir / "splat" / "training_status.json"
    status = {}
    if status_path.exists():
        status = json.loads(status_path.read_text())
    rows.append({
        "job_id": run_id,
        "dataset": run_id.split("_", 1)[0],
        "variant": variant,
        "patch_id": patch_id,
        "status": status.get("status", "unknown"),
        "training_runtime_seconds": status.get("duration_seconds", status.get("runtime_seconds", "")),
        "actual_splat_count": status.get("actual_splat_count", ""),
        "failure_reason": status.get("failure_reason", status.get("reason", "")),
    })

fields = ["job_id", "dataset", "variant", "patch_id", "status", "training_runtime_seconds", "actual_splat_count", "failure_reason"]
with (summary_dir / "results_splat_eval.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

(summary_dir / "summary.md").write_text(
    "# Scratch Ablation Eval\n\n"
    f"- run_id: `{run_id}`\n"
    f"- variant: `{variant}`\n"
    f"- selected patches: `{patch_list}`\n"
    f"- patch count: {len(patch_ids)}\n",
    encoding="utf-8",
)
PY
}

write_stage1_config() {
  if [[ -z "${STAGE1_VARIANT}" ]]; then
    echo "Set STAGE1_VARIANT for WORKER_MODE=stage1_sfm_eval." >&2
    exit 2
  fi
  "${REEFS_VENV}/bin/python" - "${DATASET_NAME}" "${CONFIG_PATH}" "${STAGE1_VARIANT}" <<'"'"'PY'"'"'
import sys
from pathlib import Path

import yaml

dataset_name, config_path, variant_name = sys.argv[1:4]
source = yaml.safe_load(Path("experiments/ablations/ablation_config.yml").read_text())
variants = [item for item in source["sfm_variants"] if item["name"] == variant_name]
if not variants:
    raise SystemExit(f"unknown Stage 1 variant: {variant_name}")
variant = variants[0]
variant.setdefault("overrides", {})
variant["overrides"]["advanced.sfm.preflight.colmap_target_version"] = "5f35f398"
source["output_root"] = "/scratch/3dreefs/project/ablation_eval"
source["run_validation_splats_for_sfm"] = True
source["datasets"] = [{
    "name": dataset_name,
    "config": config_path,
    "project_dir": "/scratch/3dreefs/project",
}]
source["sfm_variants"] = [variant]
Path("/scratch/3dreefs/stage1_ablation_config.yml").write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
PY
}

if [[ "${WORKER_MODE}" == "stage1_sfm_eval" ]]; then
  write_stage1_config
  "${REEFS_VENV}/bin/python" experiments/ablations/ablation_experiment.py run \
    --config /scratch/3dreefs/stage1_ablation_config.yml \
    --phase all
elif [[ -n "${EVAL_PATCH_COUNT}" ]]; then
  patches_dir="/scratch/3dreefs/project/runs/${RUN_ID}/splat/patches"
  if [[ -n "${RESUME_FROM_S3_URI}" ]] && find "${patches_dir}" -mindepth 2 -maxdepth 2 -name patch_metadata.json -print -quit 2>/dev/null | grep -q .; then
    if find "${patches_dir}" -path "*/selected_images/*" -type f -print -quit 2>/dev/null | grep -q .; then
      echo "Using restored patch outputs from ${RESUME_FROM_S3_URI}; skipping sfm,splat.patch."
    else
      echo "Restored patch metadata has no selected_images; regenerating splat.patch from restored SfM outputs."
      run_pipeline "splat.patch" "overwrite"
    fi
  else
    run_pipeline "sfm,splat.patch" "${RESUME_POLICY}"
  fi
  patch_list="$(
    "${REEFS_VENV}/bin/python" - "${RUN_ID}" "${EVAL_PATCH_COUNT}" <<'"'"'PY'"'"'
import sys
from pathlib import Path
from reefs.experiments.ablations.grid import select_even_patch_ids

run_id, count = sys.argv[1], int(sys.argv[2])
patches = Path("/scratch/3dreefs/project/runs") / run_id / "splat" / "patches"
selected = select_even_patch_ids([path.name for path in patches.iterdir() if path.is_dir()], count)
print("[" + ",".join(selected) + "]")
PY
  )"
  echo "Selected eval patches: ${patch_list}"
  run_pipeline "splat.train,splat.postprocess" "resume" \
    --advanced.splat.train.patch_ids "${patch_list}" \
    --advanced.splat.train.retrain_failed true \
    --advanced.splat.cleanup.patch_ids "${patch_list}" \
    --advanced.splat.merge.patch_ids "${patch_list}"
  write_eval_summary "${patch_list}"
else
  run_pipeline "${STEPS}" "${RESUME_POLICY}"
fi
'
