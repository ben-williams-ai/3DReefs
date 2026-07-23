#!/usr/bin/env bash
set -euo pipefail

BUCKET="${BUCKET:-3dreefs-ben-eu-north1}"
INPUT_PREFIX="${INPUT_PREFIX:-input/datasets}"
OUTPUT_PREFIX="${OUTPUT_PREFIX:-experiments/ablations}"
IMAGE_NAME="${IMAGE_NAME:-cr.eu-north1.nebius.cloud/e00eqkjz0mkvvedmrd/3dreefs:colmap404-python-eval-20260722-metadata-recovery}"
IMAGE_DIGEST="${IMAGE_DIGEST:-}"
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
EVAL_TARGET_IMAGE_SOURCE="${EVAL_TARGET_IMAGE_SOURCE:-full_resolution_undistorted}"
EVAL_FULL_RES_UNDISTORTED_IMAGES_DIR="${EVAL_FULL_RES_UNDISTORTED_IMAGES_DIR:-}"
RESUME_FROM_S3_URI="${RESUME_FROM_S3_URI:-}"
WORKER_MODE="${WORKER_MODE:-pipeline}"
STAGE1_VARIANT="${STAGE1_VARIANT:-}"
SOURCE_VARIANT="${SOURCE_VARIANT:-sfm_1024_sift_global}"
SOURCE_BUNDLE_URI="${SOURCE_BUNDLE_URI:-}"
TRAINING_RESOLUTION="${TRAINING_RESOLUTION:-}"
PATCH_SIZE="${PATCH_SIZE:-}"
SPLAT_COUNTS="${SPLAT_COUNTS:-}"
COLOUR_PROFILE_URI="${COLOUR_PROFILE_URI:-}"
COLOUR_PROFILE_SHA256="${COLOUR_PROFILE_SHA256:-}"

DATASET_DIR="${SCRATCH_ROOT}/datasets/${DATASET_NAME}"
OUT_ROOT="${SCRATCH_ROOT}/runs/${RUN_ID}"
WORK_DIR="${SCRATCH_ROOT}/worker/${RUN_ID}"
REPO_DIR="${WORK_DIR}/repo"
VOCAB_TREE="${WORK_DIR}/vocab_tree.bin"
ALIKED_N16ROT_VOCAB_TREE="${WORK_DIR}/aliked_n16rot_vocab_tree.bin"
ALIKED_N32_VOCAB_TREE="${WORK_DIR}/aliked_n32_vocab_tree.bin"
EXIT_FILE="${WORK_DIR}/${RUN_ID}.exit"
RESOURCE_SAMPLE_INTERVAL_SECONDS="${RESOURCE_SAMPLE_INTERVAL_SECONDS:-30}"
RESOURCE_SAMPLES_FILE="${OUT_ROOT}/project/runs/${RUN_ID}/resource_samples.csv"
RESOURCE_SUMMARY_FILE="${OUT_ROOT}/project/runs/${RUN_ID}/resource_summary.json"
RESOURCE_SAMPLER_PID=""
COLOUR_PROFILE="${WORK_DIR}/colour_profile.json"

require_env() {
  if [[ -z "${!1:-}" ]]; then
    echo "Set $1 in the environment." >&2
    exit 2
  fi
}

aws_s3() {
  local command="$1"
  shift
  case "${command}" in
    cp|sync)
      aws s3 "${command}" "$@" --no-progress --endpoint-url "${ENDPOINT_URL}"
      ;;
    *)
      aws s3 "${command}" "$@" --endpoint-url "${ENDPOINT_URL}"
      ;;
  esac
}

start_resource_sampler() {
  mkdir -p "$(dirname "${RESOURCE_SAMPLES_FILE}")"
  printf 'timestamp_utc,ram_used_mib,gpu_memory_used_mib,gpu_utilization_percent,gpu_power_watts\n' > "${RESOURCE_SAMPLES_FILE}"
  (
    while true; do
      timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      ram_used_mib="$(awk '/MemTotal/ {total=$2} /MemAvailable/ {available=$2} END {if (total && available) printf "%.0f", (total - available) / 1024; else printf ""}' /proc/meminfo)"
      gpu_memory_used_mib=""
      gpu_utilization_percent=""
      gpu_power_watts=""
      if command -v nvidia-smi >/dev/null 2>&1; then
        gpu_line="$(nvidia-smi --query-gpu=memory.used,utilization.gpu,power.draw --format=csv,noheader,nounits 2>/dev/null | head -n 1 || true)"
        if [[ -n "${gpu_line}" ]]; then
          IFS=',' read -r gpu_memory_used_mib gpu_utilization_percent gpu_power_watts <<< "${gpu_line}"
          gpu_memory_used_mib="${gpu_memory_used_mib//[[:space:]]/}"
          gpu_utilization_percent="${gpu_utilization_percent//[[:space:]]/}"
          gpu_power_watts="${gpu_power_watts//[[:space:]]/}"
        fi
      fi
      printf '%s,%s,%s,%s,%s\n' "${timestamp}" "${ram_used_mib}" "${gpu_memory_used_mib}" "${gpu_utilization_percent}" "${gpu_power_watts}" >> "${RESOURCE_SAMPLES_FILE}"
      sleep "${RESOURCE_SAMPLE_INTERVAL_SECONDS}"
    done
  ) &
  RESOURCE_SAMPLER_PID="$!"
}

stop_resource_sampler() {
  if [[ -n "${RESOURCE_SAMPLER_PID}" ]] && kill -0 "${RESOURCE_SAMPLER_PID}" >/dev/null 2>&1; then
    kill "${RESOURCE_SAMPLER_PID}" >/dev/null 2>&1 || true
    wait "${RESOURCE_SAMPLER_PID}" 2>/dev/null || true
  fi
  RESOURCE_SAMPLER_PID=""
  if [[ -f "${RESOURCE_SAMPLES_FILE}" ]]; then
    python3 - "${RESOURCE_SAMPLES_FILE}" "${RESOURCE_SUMMARY_FILE}" <<'PY' || true
import csv
import json
import sys
from pathlib import Path

samples_path = Path(sys.argv[1])
summary_path = Path(sys.argv[2])
rows = list(csv.DictReader(samples_path.open(newline="", encoding="utf-8")))

def max_number(field: str):
    values = []
    for row in rows:
        value = row.get(field, "")
        if value == "":
            continue
        try:
            values.append(float(value))
        except ValueError:
            pass
    return max(values) if values else None

payload = {
    "samples": len(rows),
    "peak_ram_mib": max_number("ram_used_mib"),
    "peak_vram_mib": max_number("gpu_memory_used_mib"),
    "peak_gpu_utilization_percent": max_number("gpu_utilization_percent"),
    "peak_gpu_power_watts": max_number("gpu_power_watts"),
}
summary_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
  fi
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
  local upload_code=0
  local ablation_eval_dir="${OUT_ROOT}/project/ablation_eval"
  stop_resource_sampler
  mkdir -p "${WORK_DIR}"
  printf 'PIPELINE_EXIT:%s\nUPLOAD_STATUS:pending\n' "${code}" > "${EXIT_FILE}"
  if [[ "${WORKER_MODE}" == "stage2_source" || "${WORKER_MODE}" == "stage2_source_recovery" ]]; then
    printf '{"status":"pending","run_id":"%s"}\n' "${RUN_ID}" > "${WORK_DIR}/source_upload_pending.json"
    aws_s3 cp "${WORK_DIR}/source_upload_pending.json" \
      "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/source_upload_pending.json" || upload_code=1
    # Patch selected_images are generated links into the physical source
    # workspaces and are not part of the reusable source-bundle contract.
    local source_patches="${OUT_ROOT}/project/runs/${RUN_ID}/splat/patches"
    if [[ -d "${source_patches}" ]]; then
      sudo find "${source_patches}" -path "*/selected_images/*" -type l -delete
    fi
  fi
  if [[ -d "${OUT_ROOT}/project/runs/${RUN_ID}" ]]; then
    aws_s3 sync "${OUT_ROOT}/project/runs/${RUN_ID}" "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/" \
      --no-follow-symlinks || upload_code=1
  fi
  if [[ -d "${ablation_eval_dir}" ]]; then
    # These links point into container-only paths and are generated inputs, not
    # scientific outputs. Remove them only after the pipeline has finished.
    local eval_datasets_root="${ablation_eval_dir}/eval_datasets"
    if [[ -d "${eval_datasets_root}" ]]; then
      sudo find "${eval_datasets_root}" -type l -delete
    fi
    aws_s3 sync "${ablation_eval_dir}" "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/ablation_eval/" \
      --no-follow-symlinks \
      --exclude "eval_datasets/*/*/images/*" \
      --exclude "eval_datasets/*/*/sparse/0/points3D.txt" || upload_code=1
    if [[ "${code}" -eq 0 && "${upload_code}" -eq 0 ]]; then
      local eval_verify_output
      eval_verify_output="$(aws_s3 sync \
        "${ablation_eval_dir}" "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/ablation_eval/" \
        --no-follow-symlinks \
        --exclude "eval_datasets/*/*/images/*" \
        --exclude "eval_datasets/*/*/sparse/0/points3D.txt" --dryrun 2>&1)" || upload_code=1
      if [[ -n "${eval_verify_output}" ]]; then
        echo "Ablation upload verification found differences:" >&2
        printf '%s\n' "${eval_verify_output}" >&2
        upload_code=1
      fi
    fi
  fi
  if [[ "${WORKER_MODE}" == "stage1_sfm_eval" && -f "${OUT_ROOT}/project/ablation_eval/results_sfm.csv" ]]; then
    while IFS= read -r scientific_run_id; do
      [[ -n "${scientific_run_id}" ]] || continue
      local scientific_run_dir="${OUT_ROOT}/project/runs/${scientific_run_id}"
      if [[ -d "${scientific_run_dir}" ]]; then
        local scientific_destination="s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/scientific_runs/${scientific_run_id}/"
        aws_s3 sync "${scientific_run_dir}" \
          "${scientific_destination}" \
          --no-follow-symlinks || upload_code=1
        if [[ "${code}" -eq 0 && "${upload_code}" -eq 0 ]]; then
          local scientific_verify_output
          scientific_verify_output="$(aws_s3 sync \
            "${scientific_run_dir}" "${scientific_destination}" \
            --no-follow-symlinks --dryrun 2>&1)" || upload_code=1
          if [[ -n "${scientific_verify_output}" ]]; then
            echo "Scientific-run upload verification found differences for ${scientific_run_id}:" >&2
            printf '%s\n' "${scientific_verify_output}" >&2
            upload_code=1
          fi
        fi
      fi
    done < <(python3 - "${OUT_ROOT}/project/ablation_eval/results_sfm.csv" <<'PY'
import csv
import sys

with open(sys.argv[1], newline="", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        print(row["job_id"])
PY
    )
  fi
  if [[ -d "${OUT_ROOT}/project/runs" ]]; then
    while IFS= read -r -d '' run_dir; do
      local run_name
      run_name="$(basename "${run_dir}")"
      for rel_path in \
        "run_status.json" \
        "timings.json" \
        "effective_config.yml" \
        "cli_overrides.json" \
        "run_manifest.json" \
        "resource_samples.csv" \
        "resource_summary.json" \
        "logs/pipeline.log" \
        "logs/colmap.log" \
        "logs/warnings.log"; do
        if [[ -f "${run_dir}/${rel_path}" ]]; then
          aws_s3 cp "${run_dir}/${rel_path}" \
            "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/diagnostics/runs/${run_name}/${rel_path}" || upload_code=1
        fi
      done
    done < <(find "${OUT_ROOT}/project/runs" -mindepth 1 -maxdepth 1 -type d -print0)
  fi
  if [[ ( "${WORKER_MODE}" == "stage2_source" || "${WORKER_MODE}" == "stage2_source_recovery" ) && "${code}" -eq 0 && "${upload_code}" -eq 0 ]]; then
    local source_dir="${OUT_ROOT}/project/runs/${RUN_ID}"
    local verify_output
    verify_output="$(aws_s3 sync "${source_dir}" "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/" --dryrun 2>&1)" || upload_code=1
    if [[ -n "${verify_output}" ]]; then
      echo "Remote source read-back verification found differences:" >&2
      printf '%s\n' "${verify_output}" >&2
      upload_code=1
    fi
    if [[ "${upload_code}" -eq 0 ]]; then
      printf '{"status":"verified_complete","pipeline_exit":0,"upload_status":0,"run_id":"%s"}\n' \
        "${RUN_ID}" > "${source_dir}/source_complete.json"
      aws_s3 cp "${source_dir}/source_complete.json" \
        "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/source_complete.json" || upload_code=1
      if [[ "${upload_code}" -eq 0 ]]; then
        local remote_source_marker
        remote_source_marker="$(aws_s3 cp \
          "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/source_complete.json" -)" || upload_code=1
        if [[ "${upload_code}" -eq 0 && \
          "${remote_source_marker}" != "$(tr -d '\n' < "${source_dir}/source_complete.json")" ]]; then
          echo "Source completion marker read-back failed for ${RUN_ID}." >&2
          upload_code=1
        fi
      fi
    fi
  fi
  printf 'PIPELINE_EXIT:%s\nUPLOAD_STATUS:%s\n' "${code}" "${upload_code}" > "${EXIT_FILE}"
  aws_s3 cp "${EXIT_FILE}" "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/${RUN_ID}.exit" || upload_code=1
  return "${upload_code}"
}

upload_completed_stage2_probes() {
  local manifests_root="${OUT_ROOT}/project/ablation_eval/probe_manifests"
  local eval_datasets_root="${OUT_ROOT}/project/ablation_eval/eval_datasets"
  [[ -d "${manifests_root}" ]] || return 0
  while IFS= read -r -d '' marker; do
    local probe_id ack verify_output
    probe_id="$(basename "$(dirname "${marker}")")"
    ack="${OUT_ROOT}/stage2_upload_ack/${probe_id}"
    [[ -f "${ack}" ]] && continue
    # These generated inputs use container-only absolute targets. Remove the
    # links after local validation so host-side AWS CLI traversal cannot fail.
    if [[ -d "${eval_datasets_root}" ]]; then
      sudo find "${eval_datasets_root}" -type l -delete
    fi
    aws_s3 sync "${OUT_ROOT}/project/ablation_eval" \
      "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/ablation_eval/" \
      --no-follow-symlinks \
      --exclude "eval_datasets/*/*/images/*" \
      --exclude "eval_datasets/*/*/sparse/0/points3D.txt"
    verify_output="$(aws_s3 sync "${OUT_ROOT}/project/ablation_eval" \
      "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/ablation_eval/" \
      --no-follow-symlinks \
      --exclude "eval_datasets/*/*/images/*" \
      --exclude "eval_datasets/*/*/sparse/0/points3D.txt" --dryrun 2>&1)"
    if [[ -n "${verify_output}" ]]; then
      echo "Stage 2 probe upload verification failed for ${probe_id}:" >&2
      printf '%s\n' "${verify_output}" >&2
      return 1
    fi
    printf '{"status":"verified_uploaded","probe_id":"%s","upload_status":0}\n' \
      "${probe_id}" > "$(dirname "${marker}")/probe_upload_complete.json"
    aws_s3 cp "$(dirname "${marker}")/probe_upload_complete.json" \
      "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/ablation_eval/probe_manifests/${probe_id}/probe_upload_complete.json"
    local remote_marker
    remote_marker="$(aws_s3 cp \
      "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/ablation_eval/probe_manifests/${probe_id}/probe_upload_complete.json" -)"
    [[ "${remote_marker}" == "$(tr -d '\n' < "$(dirname "${marker}")/probe_upload_complete.json")" ]] || {
      echo "Stage 2 probe upload marker read-back failed for ${probe_id}." >&2
      return 1
    }
    mkdir -p "$(dirname "${ack}")"
    printf 'UPLOAD_STATUS:0\n' > "${ack}"
    echo "Verified Stage 2 probe upload: ${probe_id}"
  done < <(find "${manifests_root}" -mindepth 2 -maxdepth 2 -name probe_complete.json -print0)
}

require_env AWS_ACCESS_KEY_ID
require_env AWS_SECRET_ACCESS_KEY

trap 'code=$?; upload_outputs "${code}"; upload_code=$?; if [[ "${code}" -eq 0 && "${upload_code}" -ne 0 ]]; then exit "${upload_code}"; fi; exit "${code}"' EXIT

sudo apt-get update
sudo apt-get install -y --no-install-recommends ca-certificates curl git unzip zstd
ensure_aws_cli

mkdir -p "${DATASET_DIR}" "${WORK_DIR}" "${OUT_ROOT}"
cd "${WORK_DIR}"

if [[ "${WORKER_MODE}" == "stage2_splat_eval" ]]; then
  require_env SOURCE_BUNDLE_URI
  require_env TRAINING_RESOLUTION
  require_env PATCH_SIZE
  require_env SPLAT_COUNTS
  mkdir -p "${DATASET_DIR}/raw_images"
  SOURCE_LOCAL_RUN_ID="sfm_${DATASET_NAME}_${SOURCE_VARIANT}"
  mkdir -p "${OUT_ROOT}/project/runs/${SOURCE_LOCAL_RUN_ID}"
  case "${TRAINING_RESOLUTION}" in
    1024) TRAINING_WORKSPACE="undistorted" ;;
    2048) TRAINING_WORKSPACE="undistorted_2048" ;;
    full) TRAINING_WORKSPACE="undistorted_full_resolution" ;;
    *) echo "Unsupported Stage 2 training resolution: ${TRAINING_RESOLUTION}" >&2; exit 2 ;;
  esac
  source_sync_args=(
    --exclude "*"
    --include "source_manifest.json"
    --include "source_complete.json"
    --include "checksums.sha256"
    --include "worker_identity.json"
    --include "effective_config.yml"
    --include "run_manifest.json"
    --include "stage2_patch_layouts/*"
    --include "sfm/database.db"
    --include "sfm/image_mapping.json"
    --include "sfm/sparse/*"
    --include "sfm/selected_sparse/*"
    --include "sfm/${TRAINING_WORKSPACE}/*"
    --include "sfm/undistorted_full_resolution/*"
  )
  aws_s3 sync "${SOURCE_BUNDLE_URI%/}/" "${OUT_ROOT}/project/runs/${SOURCE_LOCAL_RUN_ID}/" \
    "${source_sync_args[@]}"
  test -f "${OUT_ROOT}/project/runs/${SOURCE_LOCAL_RUN_ID}/source_manifest.json"
  test -f "${OUT_ROOT}/project/runs/${SOURCE_LOCAL_RUN_ID}/source_complete.json"
  test -f "${OUT_ROOT}/project/runs/${SOURCE_LOCAL_RUN_ID}/checksums.sha256"
  rmdir "${DATASET_DIR}/raw_images"
  ln -s "${OUT_ROOT}/project/runs/${SOURCE_LOCAL_RUN_ID}/sfm/${TRAINING_WORKSPACE}/images" \
    "${DATASET_DIR}/raw_images"
else
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
fi

if [[ -n "${RESUME_FROM_S3_URI}" ]]; then
  mkdir -p "${OUT_ROOT}/project/runs/${RUN_ID}"
  aws_s3 sync "${RESUME_FROM_S3_URI%/}/" "${OUT_ROOT}/project/runs/${RUN_ID}/" \
    --exclude "ablation_eval/*"
  if aws_s3 ls "${RESUME_FROM_S3_URI%/}/ablation_eval/" >/dev/null 2>&1; then
    mkdir -p "${OUT_ROOT}/project/ablation_eval"
    aws_s3 sync "${RESUME_FROM_S3_URI%/}/ablation_eval/" "${OUT_ROOT}/project/ablation_eval/"
  fi
fi

if [[ -n "${COLOUR_PROFILE_URI}" ]]; then
  require_env COLOUR_PROFILE_SHA256
  aws_s3 cp "${COLOUR_PROFILE_URI}" "${COLOUR_PROFILE}"
  [[ "$(sha256sum "${COLOUR_PROFILE}" | awk '{print $1}')" == "${COLOUR_PROFILE_SHA256}" ]] || {
    echo "Colour profile checksum mismatch." >&2
    exit 1
  }
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

if [[ "${WORKER_MODE}" != "stage2_splat_eval" && -z "${VOCAB_TREE_S3_URI:-}" ]]; then
  echo "Set VOCAB_TREE_S3_URI; refusing to create an empty vocab-tree placeholder." >&2
  exit 2
fi
if [[ -n "${VOCAB_TREE_S3_URI:-}" ]]; then
  aws_s3 cp "${VOCAB_TREE_S3_URI}" "${VOCAB_TREE}"
fi
if [[ -n "${ALIKED_N16ROT_VOCAB_TREE_S3_URI:-}" ]]; then
  aws_s3 cp "${ALIKED_N16ROT_VOCAB_TREE_S3_URI}" "${ALIKED_N16ROT_VOCAB_TREE}"
fi
if [[ -n "${ALIKED_N32_VOCAB_TREE_S3_URI:-}" ]]; then
  aws_s3 cp "${ALIKED_N32_VOCAB_TREE_S3_URI}" "${ALIKED_N32_VOCAB_TREE}"
fi

docker_args=(
  --rm
  --gpus all
  --shm-size="${SHM_SIZE}" \
  -e HOME="/scratch/3dreefs/home" \
  -e IMAGE_NAME="${IMAGE_NAME}" \
  -e IMAGE_DIGEST="${IMAGE_DIGEST}" \
  -e GIT_REPO="${GIT_REPO}" \
  -e GIT_REF="${GIT_REF}" \
  -e CONFIG_IN_REPO="${CONFIG_IN_REPO}" \
  -e VOCAB_TREE_PATH="/input/vocab_tree.bin" \
  -e ALIKED_N16ROT_VOCAB_TREE_PATH="/input/aliked_n16rot_vocab_tree.bin" \
  -e ALIKED_N32_VOCAB_TREE_PATH="/input/aliked_n32_vocab_tree.bin" \
  -e DATASET_NAME="${DATASET_NAME}" \
  -e RUN_ID="${RUN_ID}" \
  -e STEPS="${STEPS}" \
  -e RESUME_POLICY="${RESUME_POLICY}" \
  -e EXTRA_ARGS="${EXTRA_ARGS}" \
  -e EVAL_PATCH_COUNT="${EVAL_PATCH_COUNT}" \
  -e EVAL_VARIANT="${EVAL_VARIANT}" \
  -e EVAL_TARGET_IMAGE_SOURCE="${EVAL_TARGET_IMAGE_SOURCE}" \
  -e EVAL_FULL_RES_UNDISTORTED_IMAGES_DIR="${EVAL_FULL_RES_UNDISTORTED_IMAGES_DIR}" \
  -e WORKER_MODE="${WORKER_MODE}" \
  -e STAGE1_VARIANT="${STAGE1_VARIANT}" \
  -e SOURCE_VARIANT="${SOURCE_VARIANT}" \
  -e SOURCE_BUNDLE_URI="${SOURCE_BUNDLE_URI}" \
  -e TRAINING_RESOLUTION="${TRAINING_RESOLUTION}" \
  -e PATCH_SIZE="${PATCH_SIZE}" \
  -e SPLAT_COUNTS="${SPLAT_COUNTS}" \
  -e RESUME_FROM_S3_URI="${RESUME_FROM_S3_URI}" \
  -e COLOUR_PROFILE_SHA256="${COLOUR_PROFILE_SHA256}" \
  -v "${DATASET_DIR}:/input/dataset:ro" \
  -v "${DATASET_DIR}/raw_images:/scratch/3dreefs/project/raw_images:ro" \
  -v "${OUT_ROOT}:/scratch/3dreefs"
)
if [[ -f "${VOCAB_TREE}" ]]; then
  docker_args+=(-v "${VOCAB_TREE}:/input/vocab_tree.bin:ro")
fi
if [[ -f "${ALIKED_N16ROT_VOCAB_TREE}" ]]; then
  docker_args+=(-v "${ALIKED_N16ROT_VOCAB_TREE}:/input/aliked_n16rot_vocab_tree.bin:ro")
fi
if [[ -f "${ALIKED_N32_VOCAB_TREE}" ]]; then
  docker_args+=(-v "${ALIKED_N32_VOCAB_TREE}:/input/aliked_n32_vocab_tree.bin:ro")
fi
if [[ -n "${CONFIG}" ]]; then
  docker_args+=(-v "${CONFIG}:/job/config.yml:ro")
fi
if [[ -n "${PATCH_FILE}" ]]; then
  docker_args+=(-v "${PATCH_FILE}:/job/repo.patch:ro")
fi
if [[ -f "${COLOUR_PROFILE}" ]]; then
  docker_args+=(-v "${COLOUR_PROFILE}:/job/colour_profile.json:ro")
fi

sudo docker pull -q "${IMAGE_NAME}"
start_resource_sampler
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
if [[ -f /job/colour_profile.json ]]; then
  PROFILE_CONFIG=/scratch/3dreefs/profile-config.yml
  python - "${CONFIG_PATH}" "${PROFILE_CONFIG}" <<'PY'
import sys
from pathlib import Path
import yaml

source, destination = map(Path, sys.argv[1:])
config = yaml.safe_load(source.read_text(encoding="utf-8"))
config["colour_restoration"] = {
    "mode": "profile",
    "profile_path": "/job/colour_profile.json",
    "overwrite": False,
    "start_sfm_immediately": True,
}
destination.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
PY
  CONFIG_PATH="${PROFILE_CONFIG}"
fi

cat > /scratch/3dreefs/git_checkout.env <<EOF
GIT_REPO=${GIT_REPO}
GIT_REF=${GIT_REF}
GIT_COMMIT=${COMMIT}
EOF

mkdir -p "/scratch/3dreefs/project/runs/${RUN_ID}"
cat > "/scratch/3dreefs/project/runs/${RUN_ID}/worker_identity.json" <<EOF
{
  "image_name": "${IMAGE_NAME}",
  "image_digest": "${IMAGE_DIGEST}",
  "git_repo": "${GIT_REPO}",
  "git_ref": "${GIT_REF}",
  "git_commit": "${COMMIT}",
  "config_in_repo": "${CONFIG_IN_REPO}",
  "dataset_name": "${DATASET_NAME}",
  "run_id": "${RUN_ID}",
  "worker_mode": "${WORKER_MODE}",
  "source_variant": "${SOURCE_VARIANT}",
  "source_bundle_uri": "${SOURCE_BUNDLE_URI}",
  "training_resolution": "${TRAINING_RESOLUTION}",
  "patch_size": "${PATCH_SIZE}",
  "splat_counts": "${SPLAT_COUNTS}",
  "colour_profile_sha256": "${COLOUR_PROFILE_SHA256}"
}
EOF
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

write_stage1_config() {
  if [[ -z "${STAGE1_VARIANT}" ]]; then
    echo "Set STAGE1_VARIANT for WORKER_MODE=stage1_sfm_eval." >&2
    exit 2
  fi
  "${REEFS_VENV}/bin/python" - "${DATASET_NAME}" "${CONFIG_PATH}" "${STAGE1_VARIANT}" <<'"'"'PY'"'"'
import os
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
source.setdefault("aims_baseline_overrides", {})["advanced.sfm.preflight.colmap_target_version"] = "9c23f694"
variant["overrides"]["advanced.sfm.preflight.colmap_target_version"] = "9c23f694"
source["output_root"] = "/scratch/3dreefs/project/ablation_eval"
source["run_validation_splats_for_sfm"] = True
source["datasets"] = [{
    "name": dataset_name,
    "config": config_path,
    "project_dir": "/scratch/3dreefs/project",
}]
target_source = os.environ.get("EVAL_TARGET_IMAGE_SOURCE", "full_resolution_undistorted")
source.setdefault("validation", {})["target_image_source"] = target_source
if target_source == "full_resolution_undistorted":
    full_res_dir = os.environ.get("EVAL_FULL_RES_UNDISTORTED_IMAGES_DIR")
    if full_res_dir:
        source["validation"]["full_resolution_undistorted_images_dir"] = full_res_dir
    source["validation"]["allow_full_resolution_target"] = True
source["sfm_variants"] = [variant]
Path("/scratch/3dreefs/stage1_ablation_config.yml").write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
PY
}

write_stage2_config() {
  "${REEFS_VENV}/bin/python" - "${DATASET_NAME}" "${CONFIG_PATH}" "${SOURCE_VARIANT}" \
    "${TRAINING_RESOLUTION}" "${PATCH_SIZE}" "${SPLAT_COUNTS}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

import yaml

dataset_name, config_path, variant_name, resolution, patch_size, splat_counts = sys.argv[1:7]
source = yaml.safe_load(Path("experiments/ablations/ablation_config.yml").read_text(encoding="utf-8"))
variants = [item for item in source["sfm_variants"] if item["name"] == variant_name]
if len(variants) != 1:
    raise SystemExit(f"expected exactly one source variant: {variant_name}")
source["output_root"] = "/scratch/3dreefs/project/ablation_eval"
source["datasets"] = [{
    "name": dataset_name,
    "config": config_path,
    "project_dir": "/scratch/3dreefs/project",
}]
source["sfm_variants"] = variants
grid = source.setdefault("splat_grid", {})
grid["training_resolutions"] = [resolution]
grid["patch_sizes"] = [int(patch_size)]
grid["splat_counts"] = [int(value) for value in splat_counts.split(",")]
grid["max_widths"] = []
grid["training_image_source"] = "training_undistorted"
grid["eval_target_image_source"] = "full_resolution_undistorted"
grid["eval_steps"] = [30000]
source_manifest = Path("/scratch/3dreefs/project/runs") / f"sfm_{dataset_name}_{variant_name}" / "source_manifest.json"
grid["source_bundle_id"] = json.loads(source_manifest.read_text(encoding="utf-8"))["source_id"]
checksums = source_manifest.with_name("checksums.sha256")
grid["source_bundle_checksum"] = hashlib.sha256(checksums.read_bytes()).hexdigest()
source.setdefault("validation", {})["patch_count"] = 10
Path("/scratch/3dreefs/stage2_ablation_config.yml").write_text(
    yaml.safe_dump(source, sort_keys=False),
    encoding="utf-8",
)
PY
}

run_stage2_batch() {
  local source_local_run_id="sfm_${DATASET_NAME}_${SOURCE_VARIANT}"
  local source_run_dir="/scratch/3dreefs/project/runs/${source_local_run_id}"
  "${REEFS_VENV}/bin/python" - "${source_run_dir}" "${TRAINING_RESOLUTION}" <<'PY'
import json
import sys
from pathlib import Path

from reefs.experiments.ablations.source_bundle import WORKSPACES, verify_checksums

source = Path(sys.argv[1])
resolution = sys.argv[2]
manifest = json.loads((source / "source_manifest.json").read_text(encoding="utf-8"))
complete = json.loads((source / "source_complete.json").read_text(encoding="utf-8"))
if manifest.get("status") != "validated":
    raise SystemExit("source manifest is not validated")
if manifest.get("source_variant") != "sfm_1024_sift_global":
    raise SystemExit("source manifest has the wrong SfM variant")
if complete.get("status") != "verified_complete":
    raise SystemExit("source bundle has no verified-complete marker")
verify_checksums(
    source,
    included_prefixes=[
        "worker_identity.json",
        "effective_config.yml",
        "run_manifest.json",
        "stage2_patch_layouts",
        "sfm/database.db",
        "sfm/image_mapping.json",
        "sfm/sparse",
        "sfm/selected_sparse",
        f"sfm/{WORKSPACES[resolution]}",
        "sfm/undistorted_full_resolution",
    ],
)
PY
  write_stage2_config
  IFS=',' read -r -a counts <<< "${SPLAT_COUNTS}"
  for count in "${counts[@]}"; do
    local suffix
    if (( count % 1000000 == 0 )); then
      suffix="$((count / 1000000))m"
    else
      suffix="$((count / 1000))k"
    fi
    local probe_id="splat_${DATASET_NAME}_${SOURCE_VARIANT}_res${TRAINING_RESOLUTION}_patch${PATCH_SIZE}_${suffix}"
    "${REEFS_VENV}/bin/python" experiments/ablations/ablation_experiment.py run \
      --config /scratch/3dreefs/stage2_ablation_config.yml \
      --phase splat \
      --sfm-variant "${SOURCE_VARIANT}" \
      --job-id "${probe_id}"
    "${REEFS_VENV}/bin/python" - "${source_run_dir}" "${PATCH_SIZE}" "${probe_id}" \
      "${TRAINING_RESOLUTION}" <<'PY'
import json
import sys
from pathlib import Path

from reefs.experiments.ablations.probe_validation import validate_probe_outputs

source_run, patch_size, probe_id, resolution = sys.argv[1:5]
selection = json.loads(
    (Path(source_run) / "stage2_patch_layouts" / f"patch{patch_size}" / "selection.json").read_text(
        encoding="utf-8"
    )
)
validate_probe_outputs(
    output_root=Path("/scratch/3dreefs/project/ablation_eval"),
    probe_id=probe_id,
    expected_patch_ids=[str(value) for value in selection["selected_patch_ids"]],
    training_resolution=resolution,
)
PY
    ack="/scratch/3dreefs/stage2_upload_ack/${probe_id}"
    until [[ -f "${ack}" ]]; do
      sleep 5
    done
  done
}

if [[ "${WORKER_MODE}" == "stage2_source" || "${WORKER_MODE}" == "stage2_source_recovery" ]]; then
  source_job_args=(
    "${REEFS_VENV}/bin/python" -m reefs.experiments.ablations.source_job
    --repo-root "${PWD}"
    --ablation-config experiments/ablations/ablation_config.yml
    --pipeline-config "${CONFIG_PATH}"
    --project-dir /scratch/3dreefs/project
    --dataset "${DATASET_NAME}"
    --run-id "${RUN_ID}"
    --git-commit "${COMMIT}"
    --git-ref "${GIT_REF}"
    --image-name "${IMAGE_NAME}"
    --image-digest "${IMAGE_DIGEST}"
  )
  if [[ "${WORKER_MODE}" == "stage2_source_recovery" ]]; then
    source_job_args+=(--recover-undistortion-only)
  fi
  "${source_job_args[@]}"
elif [[ "${WORKER_MODE}" == "stage2_splat_eval" ]]; then
  run_stage2_batch
elif [[ "${WORKER_MODE}" == "stage1_sfm_eval" ]]; then
  write_stage1_config
  "${REEFS_VENV}/bin/python" experiments/ablations/ablation_experiment.py run \
    --config /scratch/3dreefs/stage1_ablation_config.yml \
    --phase all
elif [[ "${WORKER_MODE}" == "preflight_only" ]]; then
  "${REEFS_VENV}/bin/python" - "${IMAGE_NAME}" "${GIT_REPO}" "${GIT_REF}" "${COMMIT}" "${CONFIG_PATH}" "${RUN_ID}" <<'"'"'PY'"'"'
import json
import subprocess
import sys
from pathlib import Path

image_name, git_repo, git_ref, git_commit, config_path, run_id = sys.argv[1:7]
run_dir = Path("/scratch/3dreefs/project/runs") / run_id
raw_images = Path("/scratch/3dreefs/project/raw_images")
vocab_tree = Path("/input/vocab_tree.bin")
colmap = subprocess.run(
    ["/opt/colmap/bin/colmap", "--help"],
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    timeout=30,
)
lfs = subprocess.run(
    ["/opt/lichtfeld-studio/build-release/LichtFeld-Studio", "--help"],
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    timeout=30,
)
payload = {
    "status": "complete",
    "image_name": image_name,
    "git_repo": git_repo,
    "git_ref": git_ref,
    "git_commit": git_commit,
    "config_path": config_path,
    "config_exists": Path(config_path).is_file(),
    "raw_images_exists": raw_images.is_dir(),
    "raw_image_sample_count": sum(1 for _ in raw_images.rglob("*") if _.is_file()),
    "vocab_tree_exists": vocab_tree.is_file(),
    "vocab_tree_size_bytes": vocab_tree.stat().st_size if vocab_tree.is_file() else 0,
    "aliked_n16rot_vocab_tree_exists": Path("/input/aliked_n16rot_vocab_tree.bin").is_file(),
    "aliked_n32_vocab_tree_exists": Path("/input/aliked_n32_vocab_tree.bin").is_file(),
    "colmap_help_exit_code": colmap.returncode,
    "colmap_help_first_line": colmap.stdout.splitlines()[0] if colmap.stdout.splitlines() else "",
    "lfs_help_exit_code": lfs.returncode,
    "lfs_help_first_line": lfs.stdout.splitlines()[0] if lfs.stdout.splitlines() else "",
}
if not payload["config_exists"] or not payload["raw_images_exists"] or payload["raw_image_sample_count"] == 0:
    payload["status"] = "failed"
if not payload["vocab_tree_exists"] or payload["vocab_tree_size_bytes"] == 0:
    payload["status"] = "failed"
(run_dir / "preflight_result.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
if payload["status"] != "complete":
    raise SystemExit(2)
PY
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
  eval_args=(
    --advanced.eval.enabled true
    --advanced.eval.target_image_source "${EVAL_TARGET_IMAGE_SOURCE}"
  )
  if [[ "${EVAL_TARGET_IMAGE_SOURCE}" == "full_resolution_undistorted" && -n "${EVAL_FULL_RES_UNDISTORTED_IMAGES_DIR}" ]]; then
    eval_args+=(--advanced.eval.full_resolution_undistorted_images_dir "${EVAL_FULL_RES_UNDISTORTED_IMAGES_DIR}")
  fi
  run_pipeline "splat.train,splat.eval" "overwrite" \
    "${eval_args[@]}" \
    --advanced.splat.train.patch_ids "${patch_list}" \
    --advanced.splat.train.retrain_failed true \
    --advanced.splat.cleanup.patch_ids "${patch_list}" \
    --advanced.splat.merge.patch_ids "${patch_list}"
else
  run_pipeline "${STEPS}" "${RESUME_POLICY}"
fi
' &
docker_pid="$!"
if [[ "${WORKER_MODE}" == "stage2_splat_eval" ]]; then
  while kill -0 "${docker_pid}" >/dev/null 2>&1; do
    upload_completed_stage2_probes
    sleep 5
  done
  upload_completed_stage2_probes
fi
if wait "${docker_pid}"
then
  docker_code=0
else
  docker_code="$?"
fi
stop_resource_sampler
exit "${docker_code}"
