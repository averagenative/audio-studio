#!/usr/bin/env bash
# Serve the self-populating audio gallery (nginx) over the output/ dir.
# Host port 8212 -> container 80. Default binds 0.0.0.0 (LAN-visible, no auth).
set -euo pipefail
CONTAINER="audio-studio-gallery"
BIND="${GALLERY_BIND:-0.0.0.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if podman container exists "$CONTAINER"; then
  echo "Container '$CONTAINER' already exists. Stop it with: gallery-down.sh" >&2
  exit 1
fi

echo "Serving gallery -> http://$BIND:8212  (LAN: http://192.168.88.68:8212)"
exec podman run --rm -d \
  --name "$CONTAINER" \
  --security-opt=label=disable \
  -p "$BIND:8212:80" \
  -v "$ROOT/gallery/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$ROOT/gallery/index.html:/srv/gallery/index.html:ro" \
  -v "$ROOT/output:/srv/output:ro" \
  docker.io/library/nginx:alpine
