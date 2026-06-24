#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-3dreefs:local}"

docker run --rm --gpus all "${IMAGE_NAME}" 'nvidia-smi && python - <<'"'"'PY'"'"'
import torch

print("torch_cuda_available", torch.cuda.is_available())
if torch.cuda.is_available():
    print("torch_device", torch.cuda.get_device_name(0))
PY'
