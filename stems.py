#!/usr/bin/env python3
"""Split a generated track into stems (vocals / drums / bass / other) with openunmix,
for importing into a DAW — e.g. mute the AI guitar and re-amp your own over it.

Runs inside the audio-studio ComfyUI container (torch + GPU). Loads/saves via
soundfile (the container's torchaudio.load needs TorchCodec, which we sidestep).
Output: output/stems/<trackname>/{vocals,drums,bass,other}.wav

Usage:
  python3 stems.py output/song_00019.flac
  python3 stems.py song_00019.flac --model umxhq    # umxl (default) or umxhq
"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CONTAINER = "audio-studio-comfyui"

SEP = r'''
import soundfile as sf, torch, os, sys
from openunmix import predict
name = sys.argv[1]; model = sys.argv[2]
audio, rate = sf.read(f"/root/ComfyUI/output/{name}", dtype="float32")
if audio.ndim == 1: audio = audio[:, None]
ten = torch.as_tensor(audio.T).float()
est = predict.separate(audio=ten, rate=rate, model_str_or_path=model,
                       device="cuda" if torch.cuda.is_available() else "cpu")
out = f"/root/ComfyUI/output/stems/{os.path.splitext(name)[0]}"; os.makedirs(out, exist_ok=True)
for stem, t in est.items():
    sf.write(os.path.join(out, stem + ".wav"), t[0].cpu().numpy().T, rate)
    print("  wrote", stem + ".wav")
'''

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); sys.exit(1)
    model = "umxl"
    if "--model" in args:
        i = args.index("--model"); model = args[i + 1]; del args[i:i + 2]
    name = os.path.basename(args[0])
    if not os.path.exists(os.path.join(ROOT, "output", name)):
        print(f"not found: output/{name}", file=sys.stderr); sys.exit(1)
    if subprocess.run(["podman", "container", "exists", CONTAINER]).returncode != 0:
        print(f"{CONTAINER} not running — start it with ./studio-up.sh", file=sys.stderr); sys.exit(1)

    print(f"separating {name} with {model} (first run downloads the model)…")
    r = subprocess.run(["podman", "exec", "-e", "TORCH_HOME=/root/ComfyUI/models/.torch",
                        CONTAINER, "python3", "-c", SEP, name, model])
    if r.returncode != 0:
        print("separation failed", file=sys.stderr); sys.exit(1)
    print("stems ->", os.path.join(ROOT, "output", "stems", os.path.splitext(name)[0]))

if __name__ == "__main__":
    main()
