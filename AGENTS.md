# AGENTS.md

Instructions for AI coding agents working in this repo. Read [README.md](README.md)
first — its "How it works" diagram is the architecture.

## What this is

A local music studio: a ComfyUI container running **ACE-Step 1.5** + an nginx audio
gallery + `stems.py` (openunmix) + the **openDAW** web DAW, glued by `generate.py`.
The system contract: **a FLAC + a `<file>.json` sidecar land in `output/`, and the
gallery shows/plays them.** Preserve that.

## Map

| Path                 | Role                                                            |
|----------------------|----------------------------------------------------------------|
| `generate.py`        | Client. Builds ACE-Step graphs, POSTs, peak-normalizes, sidecars.|
| `stems.py`           | Stem separation via openunmix (runs in the container).         |
| `studio-*.sh`        | Start/stop ComfyUI (`audio-studio-comfyui`, host :8210).       |
| `gallery-*.sh`       | Start/stop the audio gallery (`audio-studio-gallery`, :8212).  |
| `daw-*.sh`           | Start/stop openDAW (vite dev server, https://localhost:8080).  |
| `gallery/index.html` | The whole gallery UI — one static file, polls `/list/` every 5s.|
| `setup.sh`           | Fetch model + custom node pack + openDAW.                      |
| `vendor/openDAW/`    | The web DAW (gitignored; cloned by setup.sh).                  |

`models/`, `output/`, `input/`, `user/`, `custom_nodes/`, `vendor/` are **gitignored**.

## Hard-won facts (don't regress these)

- **The correct ACE-Step turbo graph** (in `generate.py`): cfg **1.0**, steps **12**,
  `CLIPSetLastLayer -2`. Higher cfg over-drives → "clipping"; this combo is clean and
  **fixes the early-cutout** (tracks were ending short + padding silence). These came
  from the reference workflows in the `ComfyUI_RyanOnTheInside` node pack's examples.
- **Two cfg knobs:** KSampler `--cfg` (keep ~1 on turbo) vs the LM `cfg_scale` (2.0).
- **Output is peak-normalized to −1 dB** with *linear* gain (no loudness compression →
  dynamics preserved). loudnorm was wrong (muddied dynamic music).
- **Key/BPM go in `--key`/`--bpm`, never in tags.** Minor key for heavy/sad.
- **Avoid synth-implying tags** ("sub bass", "808") for real instruments.
- **Rhythm-guitar timbre is ACE-Step's ceiling** (renders synth-ish). Don't chase it
  in the model — that's what stems + DAW (record real guitar) are for.
- **XL SFT is a dead end in native ComfyUI** — its `qwen_4b_ace15` encoder has a 217k
  vocab that ComfyUI's `ace` CLIP type can't load (builds 151,936). Don't re-attempt
  without a custom encoder loader. Every expert example uses the **turbo AIO** anyway.

## Container notes

- ComfyUI image is `localhost/comfyui-ace-xl` (ComfyUI 0.26.0, baked custom-node deps).
  Fallback: `STUDIO_IMAGE=docker.io/yanwk/comfyui-boot:cu126-slim ./studio-up.sh`.
- **`/root` is a VOLUME** in the base image → `podman commit` does NOT capture
  `/root/ComfyUI` or `/root/.local`. To persist a ComfyUI change, update the bundle at
  `/default-comfyui-bundle/ComfyUI`; to persist pip deps, install `--no-user`
  (system-wide), then `podman commit`. New model/LoRA files just need a container restart.

## Conventions

- `generate.py` / `stems.py` are **standard-library only** on the host (work via
  `podman exec`). Keep them dependency-free.
- Comments on their own lines. Bash: `set -euo pipefail`, idempotent guards.
- **No CI / GitHub Actions.**

## Verify a change

```bash
./studio-up.sh && ./gallery-up.sh
until curl -sf http://127.0.0.1:8210/system_stats >/dev/null; do sleep 1; done
python3 generate.py "a smoke test, mellow synth" --instrumental --seconds 12
curl -s http://127.0.0.1:8210/queue   # past validation = generating
```
