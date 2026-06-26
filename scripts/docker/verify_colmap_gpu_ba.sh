#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-3dreefs:local}"
LOG_FILE="${LOG_FILE:-}"

docker run --rm \
  ${LOG_FILE:+-v "${LOG_FILE}:/tmp/colmap.log:ro"} \
  "${IMAGE_NAME}" '
set -euo pipefail

COLMAP_BIN="${COLMAP_BIN:-/opt/colmap/bin/colmap}"
CUDSS_WARN="Requested to use GPU for bundle adjustment, but Ceres was compiled without cuDSS support."
CUDA_WARN="Requested to use GPU for bundle adjustment, but Ceres was compiled without CUDA support."

"${COLMAP_BIN}" -h | head -n 5
"${COLMAP_BIN}" -h | grep -qi "with CUDA"
"${COLMAP_BIN}" help | grep -q "^  global_mapper$"

ceres_line="$(ldd "${COLMAP_BIN}" | grep -i libceres || true)"
echo "${ceres_line}"
ceres_path="$(ldd "${COLMAP_BIN}" | awk "/libceres/{print \$3; exit}")"
ceres_real="$(readlink -f "${ceres_path}")"
echo "COLMAP Ceres: ${ceres_real}"
case "${ceres_real}" in
  /opt/colmap/lib/*) ;;
  *) echo "COLMAP is not linked to /opt/colmap Ceres" >&2; exit 1 ;;
esac

if ldd "${COLMAP_BIN}" | grep -qi cudss; then
  ldd "${COLMAP_BIN}" | grep -i cudss
elif strings "${COLMAP_BIN}" | grep -qi cudss; then
  echo "cuDSS symbols detected in COLMAP binary"
elif [ -f /opt/colmap/include/ceres/internal/config.h ] \
  && ! grep -Eq "^[[:space:]]*#define[[:space:]]+CERES_NO_CUDSS" /opt/colmap/include/ceres/internal/config.h; then
  echo "Ceres config indicates cuDSS support"
else
  echo "cuDSS support not detected" >&2
  exit 1
fi

if [ -f /tmp/colmap.log ]; then
  cuda_count="$(grep -F -c "${CUDA_WARN}" /tmp/colmap.log || true)"
  cudss_count="$(grep -F -c "${CUDSS_WARN}" /tmp/colmap.log || true)"
  echo "Ceres fallback warnings: cuda=${cuda_count}, cudss=${cudss_count}"
  if [ "${cuda_count}" -ne 0 ] || [ "${cudss_count}" -ne 0 ]; then
    exit 1
  fi
fi

echo "COLMAP full-GPU BA verification passed"
'
