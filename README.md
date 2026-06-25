# audio-studio

A self-hosted **local music studio**: text-to-music with vocals & lyrics, a
self-populating audio gallery, **stem separation**, and a **web DAW** to record
your own instruments over the AI-generated track. Runs
[ACE-Step 1.5](https://github.com/ace-step/ACE-Step) in
[ComfyUI](https://github.com/comfyanonymous/ComfyUI) on your own GPU.

No cloud, no API keys, no per-song cost. Built and tested on Fedora with an 8 GB
NVIDIA GPU (RTX 4060 Laptop), rootless Podman, and a quantized model so it fits.

```bash
python3 generate.py "dream pop, shimmering guitars, female vocals, dreamy" \
  --lyrics "[verse]...\n[chorus]..." --seconds 90
#  -> output/song_00001.flac   (appears in the gallery with a player)
```

Sibling project to [image-studio](https://github.com/averagenative/image-studio) —
same shape (ComfyUI container + self-populating gallery), for audio.

---

## How it works

```
                         generate.py
                 (builds an ACE-Step graph, POSTs it,
                  peak-normalizes + writes a sidecar)
                              │  HTTP :8210
                              ▼
   ┌──────────────────────────────────────────┐
   │  audio-studio-comfyui  (ComfyUI+ACE-Step) │   GPU
   │  loads model, samples, decodes audio ─────┼──► output/  ◄─┐
   └──────────────────────────────────────────┘               │ shared
        ▲                                                      │
        │ stems.py (openunmix)  ── vocals/drums/bass/other ────┤
        ▼                                                      │
   ┌──────────────────────────────────────────┐               │
   │  audio-studio-gallery (nginx)             │   reads ──────┘
   │  /list/ JSON feed · /audio/ players       │
   └──────────────────────────────────────────┘
                              ▲  HTTP :8212
                     browser, auto-refresh 5s
```

- **`generate.py`** builds an ACE-Step 1.5 ComfyUI graph from your style tags +
  lyrics, POSTs it, then peak-normalizes the result and writes a `<file>.json`
  sidecar (style/lyrics/params) the gallery reads.
- **ComfyUI** runs ACE-Step on the GPU and saves a FLAC into the shared `output/`.
- **The gallery** (just nginx + one static page) serves an auto-refreshing feed
  with inline players and captions. Zero app code.
- **`stems.py`** splits any track into vocals/drums/bass/other (openunmix) for a DAW.

---

## Requirements

- Linux + **rootless Podman**, an **NVIDIA GPU** via CDI (`--device nvidia.com/gpu=all`).
  8 GB VRAM is enough for the turbo model.
- `git`, `curl`, `python3`, `ffmpeg` (for peak-normalize) on the host.
- ~25 GB disk for models + LoRAs.

---

## Setup

```bash
git clone https://github.com/averagenative/audio-studio.git
cd audio-studio
./setup.sh            # fetch ACE-Step model + openDAW (one time)
./studio-up.sh        # start ComfyUI  (host :8210)
./gallery-up.sh       # start gallery  (host :8212)
python3 generate.py "lofi hip hop, mellow piano, vinyl crackle" --instrumental
```

Gallery: <http://127.0.0.1:8212> (or `http://<your-lan-ip>:8212`).

---

## Usage

### Make a song

```bash
python3 generate.py "STYLE TAGS" --lyrics "[verse]...\n[chorus]..." --seconds 90
python3 generate.py "TAGS" --instrumental --seconds 60          # no vocals
python3 generate.py "TAGS" --lora synthwave-v1.safetensors --key "A minor" --bpm 110
python3 generate.py "TAGS" --lyrics-file lyrics.txt --count 3   # lyra-engine export
```

- **`tags`** = style/genre/instruments/vocal/mood/production (concrete words, not
  vague adjectives). **Don't** put key/bpm/tempo in tags — use the flags.
- **`--lyrics`** uses `[verse] [chorus] [bridge] [breakdown] [build] [drop]` markers.
  UPPERCASE = shouted/screamed; `(parens)` = backing vocals.
- 60 genre **LoRAs** in `models/loras/` (`<genre>-v1.safetensors`): metal, metalcore,
  synthwave, lofi, edm, techno, grunge, jazz, … `ls models/loras`.

### Stems → DAW

```bash
python3 stems.py output/song_00001.flac    # -> output/stems/song_00001/{vocals,drums,bass,other}.wav
./daw-up.sh                                  # open the web DAW, import the stems, record over them
```

---

## Tuning lessons (baked into generate.py)

Hard-won defaults — change them and you'll likely regress:

- **cfg 1.0, steps 12, `CLIPSetLastLayer -2`** — the correct turbo graph. Higher cfg
  over-drives into clipping; this combo is clean and **fixes early cutout** (tracks
  were ending short and padding silence).
- **Peak-normalized to −1 dB** with linear gain (no loudness compression → dynamics
  preserved). `--no-normalize` to skip.
- **Minor key for heavy/sad** (`--key "E minor"`); major reads "upbeat".
- **Avoid synth-implying tags** ("sub bass", "808") if you want real instruments.
- **`--shift 3.0`** (ModelSamplingACEStep) sharpens attack — helps heavier genres.
- **Real distorted *rhythm* guitar is ACE-Step's ceiling** (renders synth-ish); lead
  guitar comes through better. For authentic tone: generate the structure, then
  record/re-amp real guitar over the stems in the DAW.

---

## Scripts

| Script             | What it does                                              |
|--------------------|-----------------------------------------------------------|
| `setup.sh`         | Fetch ACE-Step model + openDAW                            |
| `studio-up/down.sh`| Start/stop ComfyUI (host **:8210**)                       |
| `gallery-up/down.sh`| Start/stop the audio gallery (host **:8212**)            |
| `generate.py`      | Generate a track + write the gallery sidecar              |
| `stems.py`         | Split a track into stems (openunmix) for a DAW            |
| `daw-up/down.sh`   | Serve the openDAW web DAW                                  |
| `check_updates.py` | Report newer local music models vs. installed             |

There's an `audio-studio` Claude Code skill with a guided **producer interview**
(vibe → reference bands via lyra-engine → tuned prompt → lyrics → render).

## License

MIT — see [LICENSE](LICENSE). The models (ACE-Step, LoRAs) and bundled openDAW
(AGPL-3.0) carry their own licenses; check before commercial use.
