#!/usr/bin/env bash
# Stop and remove the audio-studio ComfyUI container.
set -euo pipefail
CONTAINER="audio-studio-comfyui"
if ! podman container exists "$CONTAINER"; then
  echo "Container '$CONTAINER' not running — nothing to do."
  exit 0
fi
podman stop "$CONTAINER"
