#!/usr/bin/env bash
# Stop the openDAW dev server.
set -euo pipefail
if pkill -f "turbo run dev --filter=@opendaw/app-studio" 2>/dev/null || pkill -f "vite --clearScreen" 2>/dev/null; then
  echo "openDAW stopped."
else
  echo "openDAW not running."
fi
