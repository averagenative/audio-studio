#!/usr/bin/env bash
# Launch the openDAW web DAW (vite dev server) to remix stems / record over tracks.
# Run this in your OWN terminal — it's a long-running server (Ctrl-C to stop).
# openDAW requires HTTPS even on localhost (audio worklets need cross-origin isolation);
# this generates a self-signed cert if mkcert isn't available.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAW="$ROOT/vendor/openDAW"

[ -d "$DAW/node_modules" ] || { echo "openDAW not installed — run ./setup.sh first" >&2; exit 1; }

# certs (vite.config reads ../../../certs/localhost{,-key}.pem)
if [ ! -f "$DAW/certs/localhost-key.pem" ]; then
  mkdir -p "$DAW/certs"
  if command -v mkcert >/dev/null 2>&1; then
    ( cd "$DAW/certs" && mkcert localhost )
  else
    echo "[INFO] mkcert not found — generating a self-signed localhost cert (browser will warn once)."
    openssl req -x509 -newkey rsa:2048 -nodes \
      -keyout "$DAW/certs/localhost-key.pem" -out "$DAW/certs/localhost.pem" -days 825 \
      -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>/dev/null
  fi
fi

echo "Starting openDAW — open the https://localhost:<port> URL printed below."
echo "Load stems from output/stems/<track>/ and record your own guitar/vocals over them."
cd "$DAW"
exec npm run dev:studio
