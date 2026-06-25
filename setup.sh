#!/usr/bin/env bash
# One-time setup for audio-studio: fetch the ACE-Step music model, the openDAW
# web DAW, and (optionally) the Demucs stem-separation model. Idempotent.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

mkdir -p models/checkpoints output input user custom_nodes vendor

dl() {  # dl <url> <dest>
  local url="$1" dst="$2"
  if [ -s "$dst" ]; then echo "    skip $(basename "$dst") (exists)"; return; fi
  echo "    fetch $(basename "$dst")"
  curl -L -C - --retry 4 --retry-delay 5 -o "$dst" "$url"
}

echo "==> ACE-Step 1.5 turbo (all-in-one, ~9.4 GB) — much better vocals than v1"
# generate.py auto-prefers 1.5 if present. Set ACE_V1=1 to also grab the older v1 3.5B.
dl https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/checkpoints/ace_step_1.5_turbo_aio.safetensors \
   models/checkpoints/ace_step_1.5_turbo_aio.safetensors
if [ "${ACE_V1:-0}" = "1" ]; then
  echo "==> ACE-Step v1 3.5B (optional, ~7.7 GB)"
  dl https://huggingface.co/Comfy-Org/ACE-Step_ComfyUI_repackaged/resolve/main/all_in_one/ace_step_v1_3.5b.safetensors \
     models/checkpoints/ace_step_v1_3.5b.safetensors
fi

echo "==> ComfyUI_RyanOnTheInside node pack (ACE-Step 1.5 nodes + openunmix stems)"
if [ ! -d custom_nodes/ComfyUI_RyanOnTheInside ]; then
  git clone --depth 1 https://github.com/ryanontheinside/ComfyUI_RyanOnTheInside.git \
    custom_nodes/ComfyUI_RyanOnTheInside
  echo "    NOTE: its Python deps must be installed into the ComfyUI container, e.g.:"
  echo "      podman exec audio-studio-comfyui python3 -m pip install --no-user \\"
  echo "        -r /root/ComfyUI/custom_nodes/ComfyUI_RyanOnTheInside/requirements.txt soundfile"
  echo "    then 'podman commit audio-studio-comfyui localhost/comfyui-ace-xl:latest'"
else
  echo "    already present"
fi

echo "==> openDAW web DAW (built/served by ./daw-up.sh)"
if [ ! -d vendor/openDAW ]; then
  git clone --depth 1 https://github.com/andremichelle/openDAW.git vendor/openDAW
  ( cd vendor/openDAW && npm install --no-audit --no-fund )
else
  echo "    already present"
fi

echo
echo "Genre LoRAs (optional): 60 of them live at ryanontheinside/<genre>-acestep1.5-{v1,xl-v1}"
echo "on Hugging Face — drop the .safetensors into models/loras/ and use --lora <file>."

echo
echo "Done. Start it:   ./studio-up.sh && ./gallery-up.sh && ./daw-up.sh"
echo "Make a song:      python3 generate.py \"upbeat synthwave, female vocals\" --lyrics \"[verse]...\""
echo "Stems for a DAW:  python3 stems.py output/<song>.flac   (installs Demucs on first run)"
