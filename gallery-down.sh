#!/usr/bin/env bash
# Stop and remove the audio-studio gallery container.
set -euo pipefail
CONTAINER="audio-studio-gallery"
if ! podman container exists "$CONTAINER"; then
  echo "Container '$CONTAINER' not running — nothing to do."
  exit 0
fi
podman stop "$CONTAINER"
