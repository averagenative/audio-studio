#!/usr/bin/env bash
# Launch the audio-studio ComfyUI container (rootless Podman, GPU passthrough).
# ComfyUI has native ACE-Step / audio nodes. Host port 8210 -> container 8188.
#   studio-up.sh                      (loopback only)
#   COMFY_BIND=0.0.0.0 studio-up.sh   (LAN access — no auth)
set -euo pipefail

# Updated image with ComfyUI 0.26.0 (supports ACE-Step 1.5 XL qwen encoder).
# Fallback to the stock image: STUDIO_IMAGE=docker.io/yanwk/comfyui-boot:cu126-slim ./studio-up.sh
IMAGE="${STUDIO_IMAGE:-localhost/comfyui-ace-xl:latest}"
CONTAINER="audio-studio-comfyui"
BIND="${COMFY_BIND:-127.0.0.1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$ROOT"/{models,output,input,user,custom_nodes}

if podman container exists "$CONTAINER"; then
  echo "Container '$CONTAINER' already exists. Stop it with: studio-down.sh" >&2
  exit 1
fi

echo "Starting $CONTAINER -> http://$BIND:8210"
[ "$BIND" != "127.0.0.1" ] && echo "WARNING: ComfyUI has no auth; anyone on the LAN can use the GPU." >&2

exec podman run --rm -d \
  --name "$CONTAINER" \
  --device nvidia.com/gpu=all \
  --security-opt=label=disable \
  --security-opt=seccomp=unconfined \
  -p "$BIND:8210:8188" \
  -v "$ROOT/models:/root/ComfyUI/models:Z" \
  -v "$ROOT/output:/root/ComfyUI/output:Z" \
  -v "$ROOT/input:/root/ComfyUI/input:Z" \
  -v "$ROOT/custom_nodes:/root/ComfyUI/custom_nodes:Z" \
  -v "$ROOT/user:/root/ComfyUI/user:Z" \
  "$IMAGE"
