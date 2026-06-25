#!/usr/bin/env python3
"""audio-studio — generate music with ACE-Step on the local ComfyUI, and write a
JSON sidecar so the gallery can show the style/lyrics.

Usage:
  # a song with vocals (tags = style, --lyrics = words; use [verse]/[chorus] tags)
  generate.py "upbeat synthwave, 80s, female vocals, bright" --lyrics "[verse]\nNeon nights..."
  # instrumental backing track (no vocals — good for recording over)
  generate.py "lofi hip hop, mellow piano, vinyl crackle" --instrumental --seconds 90
  generate.py "epic orchestral trailer" --seconds 45 --seed 7 --count 3

`tags` (the positional prompt) is the musical style/genre/instrument/mood description.
ACE-Step turns tags + optional lyrics into a full mixed track. Split into stems
afterward with `stems.py` for DAW use.
"""
import argparse, glob, json, os, shutil, subprocess, sys, time, urllib.request, uuid

HOST = "http://127.0.0.1:8210"
ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(ROOT, "output")

def normalize(path, ceiling_db=-1.0):
    """Peak-normalize in place to a fixed dB ceiling using LINEAR gain — no loudness
    compression, so dynamics/transients (breakdowns!) are preserved. Just guarantees
    a headroom ceiling so nothing clips. Needs ffmpeg; no-op if missing."""
    import re
    if not shutil.which("ffmpeg"):
        return False
    probe = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
                           capture_output=True, text=True)
    m = re.search(r"max_volume:\s*(-?[\d.]+) dB", probe.stderr)
    if not m:
        return False
    gain = ceiling_db - float(m.group(1))   # linear gain to bring the peak to the ceiling
    tmp = path + ".norm.flac"
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", path,
                        "-af", f"volume={gain:.2f}dB", tmp], capture_output=True)
    if r.returncode == 0 and os.path.exists(tmp):
        os.replace(tmp, path)
        return True
    if os.path.exists(tmp):
        os.remove(tmp)
    return False

def ace_ckpt():
    """Prefer ACE-Step 1.5 (much better vocals) over v1 if it's installed."""
    ck = os.path.join(ROOT, "models", "checkpoints")
    for pat in ("ace_step_1.5*aio*.safetensors", "ace_step_1.5*.safetensors", "ace_step_v1*.safetensors"):
        hits = sorted(glob.glob(os.path.join(ck, pat)))
        if hits:
            return os.path.basename(hits[0])
    return "ace_step_v1_3.5b.safetensors"

CKPT = ace_ckpt()

IS_15 = "1.5" in CKPT  # the 1.5 model uses different ComfyUI nodes than v1

XL_UNET = "acestep_v1.5_xl_sft_bf16.safetensors"
XL_CLIP = "qwen_4b_ace15.safetensors"
XL_VAE  = "ace_1.5_vae.safetensors"

def build(tags, lyrics, seconds, seed, steps, cfg, bpm, temperature=0.85,
          key="C major", lora=None, lora_strength=1.0, model="turbo", shift=None):
    # Pick loaders by model. XL SFT = split files (better fidelity, slow on 8GB);
    # turbo/v1 = the all-in-one checkpoint.
    if model == "xl":
        loaders = {
            "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": XL_UNET, "weight_dtype": "default"}},
            "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": XL_CLIP, "type": "ace"}},
            "vae":  {"class_type": "VAELoader", "inputs": {"vae_name": XL_VAE}}}
        model_src, clip_src, vae_src, is15 = ["unet", 0], ["clip", 0], ["vae", 0], True
    else:
        loaders = {"ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}}}
        model_src, clip_src, vae_src, is15 = ["ckpt", 0], ["ckpt", 1], ["ckpt", 2], IS_15

    if lora:  # model-only diffusion LoRA, after the base model loader
        loaders["lora"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": model_src, "lora_name": lora, "strength_model": lora_strength}}
        model_src = ["lora", 0]

    if shift:  # ACE-Step model-sampling shift (denoising trajectory; can sharpen timbre)
        loaders["mshift"] = {"class_type": "ModelSamplingACEStep", "inputs": {
            "model": model_src, "shift": shift}}
        model_src = ["mshift", 0]

    dec  = {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["samp", 0], "vae": vae_src}}
    # filename_prefix without an "audio/" segment keeps files in output/ root (where the gallery looks)
    save = {"class_type": "SaveAudio", "inputs": {"audio": ["dec", 0], "filename_prefix": "song"}}
    samp = lambda: {"class_type": "KSampler", "inputs": {
        "model": model_src, "positive": ["pos", 0], "negative": ["neg", 0],
        "latent_image": ["lat", 0], "seed": seed, "steps": steps, "cfg": cfg,
        "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}}

    if is15:
        # CLIP skip -2, matching the reference ACE-Step 1.5 workflows (cleaner output)
        clipskip = {"clipskip": {"class_type": "CLIPSetLastLayer",
                                 "inputs": {"clip": clip_src, "stop_at_clip_layer": -2}}}
        clip_src = ["clipskip", 0]
        common = {"seed": seed, "bpm": bpm, "duration": seconds, "timesignature": "4",
                  "language": "en", "keyscale": key, "cfg_scale": 2.0,
                  "temperature": temperature, "top_p": 0.9, "top_k": 0, "min_p": 0.0}
        g = {**loaders, **clipskip,
             "lat": {"class_type": "EmptyAceStep1.5LatentAudio", "inputs": {"seconds": seconds, "batch_size": 1}},
             "pos": {"class_type": "TextEncodeAceStepAudio1.5", "inputs": {
                 "clip": clip_src, "tags": tags, "lyrics": lyrics, "generate_audio_codes": True, **common}},
             "neg": {"class_type": "TextEncodeAceStepAudio1.5", "inputs": {
                 "clip": clip_src, "tags": "", "lyrics": "", "generate_audio_codes": False, **common}},
             "samp": samp(), "dec": dec, "save": save}
    else:
        g = {**loaders,
             "lat": {"class_type": "EmptyAceStepLatentAudio", "inputs": {"seconds": seconds, "batch_size": 1}},
             "pos": {"class_type": "TextEncodeAceStepAudio", "inputs": {
                 "clip": clip_src, "tags": tags, "lyrics": lyrics, "lyrics_strength": 1.0}},
             "neg": {"class_type": "TextEncodeAceStepAudio", "inputs": {
                 "clip": clip_src, "tags": "", "lyrics": "", "lyrics_strength": 1.0}},
             "samp": samp(), "dec": dec, "save": save}
    return g, "save"

def queue(graph):
    body = json.dumps({"prompt": graph, "client_id": str(uuid.uuid4())}).encode()
    req = urllib.request.Request(f"{HOST}/prompt", data=body, headers={"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req))["prompt_id"]
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:1500], file=sys.stderr); sys.exit(1)

def wait(pid):
    for _ in range(1800):
        time.sleep(1)
        h = json.load(urllib.request.urlopen(f"{HOST}/history/{pid}"))
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                print("ERROR:", json.dumps(st.get("messages", st))[:1800], file=sys.stderr); return []
            return [a for o in h[pid]["outputs"].values() for a in o.get("audio", [])]
    print("timed out", file=sys.stderr); return []

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tags", help="musical style/genre/instruments/mood")
    ap.add_argument("--lyrics", default="", help="lyrics; use [verse]/[chorus]/[bridge] tags")
    ap.add_argument("--lyrics-file", help="read lyrics from a file (e.g. a lyra-engine export). "
                    "No Suno-style length gating — ACE-Step takes full-length lyrics.")
    ap.add_argument("--instrumental", action="store_true", help="no vocals (ignores --lyrics)")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--bpm", type=int, default=120, help="tempo (ACE-Step 1.5 only)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model", choices=["turbo", "xl"], default="turbo",
                    help="turbo = fast all-in-one (default); xl = XL SFT split files (best fidelity, slow on 8GB)")
    ap.add_argument("--steps", type=int, default=None, help="default: 16 turbo / 27 xl")
    ap.add_argument("--cfg", type=float, default=None, help="default: 2.5 turbo / 5.0 xl (cfg bites on SFT)")
    ap.add_argument("--no-normalize", dest="normalize", action="store_false",
                    help="skip the loudness-normalize/limiter finishing pass")
    ap.add_argument("--temperature", type=float, default=0.85,
                    help="vocal/code variation (ACE-Step 1.5); raise toward 1.0-1.1 for less 'stock' vocals")
    ap.add_argument("--key", default="C major", help="key/scale, e.g. 'E minor' (ACE-Step 1.5). "
                    "Heavy genres want a minor key — major reads 'upbeat'.")
    ap.add_argument("--lora", help="genre LoRA filename in models/loras/ (e.g. metalcore-v1.safetensors)")
    ap.add_argument("--lora-strength", type=float, default=1.0)
    ap.add_argument("--shift", type=float, default=None,
                    help="ModelSamplingACEStep shift (e.g. 3.0); off by default")
    ap.add_argument("--count", type=int, default=1)
    a = ap.parse_args()

    # model-aware defaults (turbo values match the reference ACE-Step 1.5 workflows)
    if a.steps is None: a.steps = 27 if a.model == "xl" else 12
    if a.cfg is None:   a.cfg = 5.0 if a.model == "xl" else 1.0

    # auto-match LoRA flavor to the model: XL needs -xl-v1, turbo needs -v1
    if a.lora:
        if a.model == "xl" and a.lora.endswith("-v1.safetensors") and "-xl-v1" not in a.lora:
            a.lora = a.lora.replace("-v1.safetensors", "-xl-v1.safetensors")
        elif a.model != "xl" and a.lora.endswith("-xl-v1.safetensors"):
            a.lora = a.lora.replace("-xl-v1.safetensors", "-v1.safetensors")
        lp = os.path.join(ROOT, "models", "loras", a.lora)
        if not os.path.exists(lp):
            print(f"warning: LoRA {a.lora} not found in models/loras/", file=sys.stderr)

    lyrics = a.lyrics
    if a.lyrics_file:
        with open(a.lyrics_file) as f:
            lyrics = f.read()
    if a.instrumental:
        lyrics = ""
    model_label = CKPT if a.model != "xl" else XL_UNET
    base_seed = a.seed or (int(uuid.uuid4().int) % 2_000_000_000)
    for i in range(a.count):
        seed = base_seed + i
        graph, save_id = build(a.tags, lyrics, a.seconds, seed, a.steps, a.cfg, a.bpm,
                               a.temperature, a.key, a.lora, a.lora_strength, a.model, a.shift)
        pid = queue(graph)
        print(f"[{i+1}/{a.count}] queued {a.model} seed={seed} {a.seconds:g}s steps={a.steps} cfg={a.cfg}"
              + (f" lora={a.lora}" if a.lora else "") + (" [instrumental]" if a.instrumental else ""))
        for au in wait(pid):
            rel = os.path.join(au.get("subfolder", ""), au["filename"])
            side = os.path.join(OUTPUT_DIR, rel + ".json")
            os.makedirs(os.path.dirname(side), exist_ok=True)
            norm = normalize(os.path.join(OUTPUT_DIR, rel)) if a.normalize else False
            with open(side, "w") as f:
                json.dump({"tags": a.tags, "lyrics": lyrics, "instrumental": a.instrumental,
                           "seconds": a.seconds, "bpm": a.bpm, "key": a.key, "seed": seed,
                           "steps": a.steps, "cfg": a.cfg, "temperature": a.temperature,
                           "lora": a.lora, "normalized": norm, "model": model_label}, f, indent=2)
            print("   ->", rel, "(normalized)" if norm else "")

if __name__ == "__main__":
    main()
