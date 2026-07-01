#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(nebius config get parent-id)}"
SUBNET_ID="${SUBNET_ID:?Set SUBNET_ID, e.g. vpcsubnet-...}"
JOB_ID="${JOB_ID:?Set JOB_ID}"
DATASET_NAME="${DATASET_NAME:?Set DATASET_NAME}"
RUN_ID="${RUN_ID:-${JOB_ID}}"
VM_NAME="${VM_NAME:-${JOB_ID}}"
BOOT_DISK_GIB="${BOOT_DISK_GIB:-1280}"
PLATFORM="${PLATFORM:-gpu-h100-sxm}"
PRESET="${PRESET:-1gpu-16vcpu-200gb}"
DELETE_ON_FINISH="${DELETE_ON_FINISH:-true}"
SSH_USER="${SSH_USER:-ubuntu}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519.pub}"
REMOTE_ENV="/run/3dreefs-worker.env"
REMOTE_SCRIPT="/tmp/run_ablation_worker.sh"

cleanup_vm() {
  if [[ -n "${INSTANCE_ID:-}" && "${DELETE_ON_FINISH}" == "true" ]]; then
    nebius compute instance delete "${INSTANCE_ID}" --format json >/dev/null || true
  fi
}
trap cleanup_vm EXIT

require_env() {
  if [[ -z "${!1:-}" ]]; then
    echo "Set $1 in the environment." >&2
    exit 2
  fi
}

require_env AWS_ACCESS_KEY_ID
require_env AWS_SECRET_ACCESS_KEY

USER_DATA="$(mktemp)"
ENV_FILE="$(mktemp)"
trap 'rm -f "${USER_DATA}" "${ENV_FILE}"; cleanup_vm' EXIT

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
  nebius compute instance create \
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
INSTANCE_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["metadata"]["id"])' <<< "${create_json}")"

PUBLIC_IP=""
for _ in {1..60}; do
  PUBLIC_IP="$(
    nebius compute instance get "${INSTANCE_ID}" --format json |
      python3 -c 'import json,sys; data=json.load(sys.stdin); print((data["status"]["network_interfaces"][0].get("public_ip_address") or {}).get("address", "").split("/")[0])'
  )"
  [[ -n "${PUBLIC_IP}" ]] && break
  sleep 5
done
[[ -n "${PUBLIC_IP}" ]]

for _ in {1..60}; do
  ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 "${SSH_USER}@${PUBLIC_IP}" 'true' && break
  sleep 5
done

nebius iam get-access-token |
  ssh "${SSH_USER}@${PUBLIC_IP}" 'sudo docker login cr.eu-north1.nebius.cloud --username iam --password-stdin'

printf 'AWS_ACCESS_KEY_ID=%q\n' "${AWS_ACCESS_KEY_ID}" > "${ENV_FILE}"
printf 'AWS_SECRET_ACCESS_KEY=%q\n' "${AWS_SECRET_ACCESS_KEY}" >> "${ENV_FILE}"
for name in BUCKET INPUT_PREFIX OUTPUT_PREFIX IMAGE_NAME GIT_REPO GIT_REF DATASET_NAME RUN_ID CONFIG_IN_REPO STEPS RESUME_POLICY EXTRA_ARGS VOCAB_TREE_S3_URI EVAL_PATCH_COUNT EVAL_VARIANT; do
  if [[ -n "${!name:-}" ]]; then
    printf '%s=%q\n' "${name}" "${!name}" >> "${ENV_FILE}"
  fi
done

scp scripts/nebius/run_ablation_worker.sh "${SSH_USER}@${PUBLIC_IP}:${REMOTE_SCRIPT}"
scp "${ENV_FILE}" "${SSH_USER}@${PUBLIC_IP}:/tmp/3dreefs-worker.env"
ssh "${SSH_USER}@${PUBLIC_IP}" "
  sudo install -m 600 -o root -g root /tmp/3dreefs-worker.env ${REMOTE_ENV}
  rm -f /tmp/3dreefs-worker.env
  chmod +x ${REMOTE_SCRIPT}
  sudo bash -lc 'set -a; source ${REMOTE_ENV}; rm -f ${REMOTE_ENV}; set +a; ${REMOTE_SCRIPT}'
"
