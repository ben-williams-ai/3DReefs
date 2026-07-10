#!/usr/bin/env bash
set -euo pipefail

NEBIUS_PROFILE="${NEBIUS_PROFILE:-}"
NEBIUS_ARGS=()
if [[ -n "${NEBIUS_PROFILE}" ]]; then
  NEBIUS_ARGS+=(--profile "${NEBIUS_PROFILE}")
fi

PROJECT_ID="${PROJECT_ID:-$(nebius "${NEBIUS_ARGS[@]}" config get parent-id)}"
SUBNET_ID="${SUBNET_ID:?Set SUBNET_ID, e.g. vpcsubnet-...}"
JOB_ID="${JOB_ID:?Set JOB_ID}"
DATASET_NAME="${DATASET_NAME:?Set DATASET_NAME}"
RUN_ID="${RUN_ID:-${JOB_ID}}"
VM_NAME="${VM_NAME:-${JOB_ID}}"
BOOT_DISK_GIB="${BOOT_DISK_GIB:-960}"
PLATFORM="${PLATFORM:-gpu-h100-sxm}"
PRESET="${PRESET:-1gpu-16vcpu-200gb}"
DELETE_ON_FINISH="${DELETE_ON_FINISH:-true}"
SSH_USER="${SSH_USER:-ubuntu}"
DEFAULT_SSH_KEY="$HOME/.ssh/id_ed25519.pub"
if [[ -f "$HOME/.ssh/3dreefs_nebius_ed25519.pub" ]]; then
  DEFAULT_SSH_KEY="$HOME/.ssh/3dreefs_nebius_ed25519.pub"
fi
SSH_KEY="${SSH_KEY:-${DEFAULT_SSH_KEY}}"
SSH_IDENTITY="${SSH_IDENTITY:-${SSH_KEY%.pub}}"
REMOTE_ENV="/run/3dreefs-worker.env"
REMOTE_SCRIPT="/tmp/run_ablation_worker.sh"
REMOTE_PATCH="/tmp/3dreefs-repo.patch"

cleanup_vm() {
  local code="$1"
  if [[ "${code}" -ne 0 ]]; then
    echo "Preserving Nebius instance ${INSTANCE_ID:-unknown} after non-zero worker exit ${code}." >&2
    return
  fi
  if [[ -n "${INSTANCE_ID:-}" && "${DELETE_ON_FINISH}" == "true" ]]; then
    local exit_marker
    exit_marker="$(
      aws s3 cp \
        "s3://${BUCKET}/${OUTPUT_PREFIX}/runs/${RUN_ID}/${RUN_ID}.exit" - \
        --endpoint-url "${ENDPOINT_URL:-https://storage.eu-north1.nebius.cloud}" 2>/dev/null || true
    )"
    if [[ "${exit_marker}" != "EXIT:0" && "${exit_marker}" != $'PIPELINE_EXIT:0\nUPLOAD_STATUS:0' ]]; then
      echo "Preserving Nebius instance ${INSTANCE_ID} because final S3 exit marker is not successful." >&2
      printf '%s\n' "${exit_marker:-missing exit marker}" >&2
      return
    fi
  fi
  if [[ -n "${INSTANCE_ID:-}" && "${DELETE_ON_FINISH}" == "true" ]]; then
    for attempt in 1 2 3; do
      echo "Deleting Nebius instance ${INSTANCE_ID} (attempt ${attempt}/3)..." >&2
      if nebius "${NEBIUS_ARGS[@]}" compute instance delete "${INSTANCE_ID}" --format json >/dev/null; then
        return
      fi
      sleep 10
    done
    echo "WARNING: failed to delete Nebius instance ${INSTANCE_ID}; clean it up manually." >&2
  fi
}
trap 'code=$?; cleanup_vm "${code}"' EXIT

require_env() {
  if [[ -z "${!1:-}" ]]; then
    echo "Set $1 in the environment." >&2
    exit 2
  fi
}

require_env AWS_ACCESS_KEY_ID
require_env AWS_SECRET_ACCESS_KEY
test -f "${SSH_KEY}"
test -f "${SSH_IDENTITY}"

USER_DATA="$(mktemp)"
ENV_FILE="$(mktemp)"
trap 'code=$?; rm -f "${USER_DATA}" "${ENV_FILE}"; cleanup_vm "${code}"' EXIT

cat > "${USER_DATA}" <<EOF
#cloud-config
users:
  - name: ${SSH_USER}
    groups: sudo
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - $(cat "${SSH_KEY}")
EOF

create_json="$(
  nebius "${NEBIUS_ARGS[@]}" compute instance create \
    --name "${VM_NAME}" \
    --parent-id "${PROJECT_ID}" \
    --resources-platform "${PLATFORM}" \
    --resources-preset "${PRESET}" \
    --boot-disk-managed-disk-name "${VM_NAME}-boot" \
    --boot-disk-managed-disk-type network_ssd \
    --boot-disk-managed-disk-size-gibibytes "${BOOT_DISK_GIB}" \
    --boot-disk-managed-disk-source-image-family-image-family ubuntu24.04-cuda13.0 \
    --boot-disk-managed-disk-source-image-family-parent-id project-e00public-images \
    --boot-disk-attach-mode READ_WRITE \
    --network-interfaces "[{\"name\":\"eth0\",\"ip_address\":{},\"public_ip_address\":{},\"subnet_id\":\"${SUBNET_ID}\"}]" \
    --cloud-init-user-data "$(cat "${USER_DATA}")" \
    --format json
)"
INSTANCE_ID="$(
  python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("metadata", {}).get("id", ""))' \
    <<< "${create_json}" || true
)"
if [[ -z "${INSTANCE_ID}" ]]; then
  INSTANCE_ID="$(
    nebius "${NEBIUS_ARGS[@]}" compute instance list --format json |
      VM_NAME="${VM_NAME}" python3 -c '
import json
import os
import sys

data = json.load(sys.stdin)
items = data.get("items", data) if isinstance(data, dict) else data
for item in items or []:
    metadata = item.get("metadata", {})
    if metadata.get("name") == os.environ["VM_NAME"]:
        print(metadata.get("id", ""))
        break
'
  )"
fi
[[ -n "${INSTANCE_ID}" ]]

PUBLIC_IP=""
for _ in {1..60}; do
  PUBLIC_IP="$(
    nebius "${NEBIUS_ARGS[@]}" compute instance get "${INSTANCE_ID}" --format json |
      python3 -c 'import json,sys; data=json.load(sys.stdin); print((data["status"]["network_interfaces"][0].get("public_ip_address") or {}).get("address", "").split("/")[0])'
  )"
  [[ -n "${PUBLIC_IP}" ]] && break
  sleep 5
done
[[ -n "${PUBLIC_IP}" ]]

SSH_OPTS=(-i "${SSH_IDENTITY}" -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5)
SSH_READY=false
for _ in {1..60}; do
  if ssh "${SSH_OPTS[@]}" "${SSH_USER}@${PUBLIC_IP}" 'true'; then
    SSH_READY=true
    break
  fi
  sleep 5
done
[[ "${SSH_READY}" == "true" ]]

REGISTRY_TOKEN="$(nebius "${NEBIUS_ARGS[@]}" iam get-access-token)"
REGISTRY_AUTH="$(printf 'iam:%s' "${REGISTRY_TOKEN}" | base64 -w0)"
ssh "${SSH_OPTS[@]}" "${SSH_USER}@${PUBLIC_IP}" "sudo install -m 700 -o root -g root -d /root/.docker && sudo tee /root/.docker/config.json >/dev/null" <<EOF
{"auths":{"cr.eu-north1.nebius.cloud":{"auth":"${REGISTRY_AUTH}"}}}
EOF
unset REGISTRY_TOKEN REGISTRY_AUTH

LOCAL_PATCH_FILE="${PATCH_FILE:-}"
if [[ -n "${LOCAL_PATCH_FILE}" ]]; then
  test -f "${LOCAL_PATCH_FILE}"
  PATCH_FILE="${REMOTE_PATCH}"
fi

printf 'AWS_ACCESS_KEY_ID=%q\n' "${AWS_ACCESS_KEY_ID}" > "${ENV_FILE}"
printf 'AWS_SECRET_ACCESS_KEY=%q\n' "${AWS_SECRET_ACCESS_KEY}" >> "${ENV_FILE}"
for name in BUCKET INPUT_PREFIX OUTPUT_PREFIX IMAGE_NAME IMAGE_DIGEST GIT_REPO GIT_REF DATASET_NAME RUN_ID CONFIG_IN_REPO STEPS RESUME_POLICY EXTRA_ARGS VOCAB_TREE_S3_URI ALIKED_N16ROT_VOCAB_TREE_S3_URI ALIKED_N32_VOCAB_TREE_S3_URI EVAL_PATCH_COUNT EVAL_VARIANT EVAL_TARGET_IMAGE_SOURCE EVAL_FULL_RES_UNDISTORTED_IMAGES_DIR RESUME_FROM_S3_URI WORKER_MODE STAGE1_VARIANT SOURCE_VARIANT SOURCE_BUNDLE_URI TRAINING_RESOLUTION PATCH_SIZE SPLAT_COUNTS PATCH_FILE; do
  if [[ -n "${!name:-}" ]]; then
    printf '%s=%q\n' "${name}" "${!name}" >> "${ENV_FILE}"
  fi
done

scp -i "${SSH_IDENTITY}" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new scripts/nebius/run_ablation_worker.sh "${SSH_USER}@${PUBLIC_IP}:${REMOTE_SCRIPT}"
scp -i "${SSH_IDENTITY}" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new "${ENV_FILE}" "${SSH_USER}@${PUBLIC_IP}:/tmp/3dreefs-worker.env"
if [[ -n "${LOCAL_PATCH_FILE}" ]]; then
  scp -i "${SSH_IDENTITY}" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new "${LOCAL_PATCH_FILE}" "${SSH_USER}@${PUBLIC_IP}:${REMOTE_PATCH}"
fi
ssh "${SSH_OPTS[@]}" "${SSH_USER}@${PUBLIC_IP}" "
  sudo install -m 600 -o root -g root /tmp/3dreefs-worker.env ${REMOTE_ENV}
  rm -f /tmp/3dreefs-worker.env
  chmod +x ${REMOTE_SCRIPT}
  sudo bash -lc 'set -a; source ${REMOTE_ENV}; rm -f ${REMOTE_ENV}; set +a; ${REMOTE_SCRIPT}'
"
