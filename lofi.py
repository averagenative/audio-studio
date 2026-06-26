#!/usr/bin/env python3
"""Lo-fi a track's VOCAL and lay it in a vintage tape/vinyl bed — keep the song,
degrade the voice. Separates the vocal (stems.py), runs it through a telephone band +
bit/sample crush + tape wobble, adds a constant hiss + RANDOM sparse vinyl crackle,
remixes over the drums/bass/synths, and peak-normalizes.

Usage:
  python3 lofi.py output/song_00026.flac                 # heavy crush + hiss + crackle
  python3 lofi.py song_00026.flac --crush light          # gentler
  python3 lofi.py song_00026.flac --no-crackle --warble  # tweak the recipe
Output: output/<name>_lofi.flac
"""
import argparse, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "output")

# vocal chain per crush level: telephone band + bit/sample crush + tape wobble
CRUSH = {
    "light": "highpass=f=350,lowpass=f=3200,acrusher=bits=7:samples=2:mode=log:mix=0.45,vibrato=f=5:d=0.12,volume=5dB",
    "heavy": "highpass=f=400,lowpass=f=3000,acrusher=bits=4:samples=6:mode=log:mix=0.9,vibrato=f=6:d=0.2,volume=6dB",
}

def ff(args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)

def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    return float(r.stdout.strip())

def peak_normalize(path, ceiling=-1.0):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"max_volume:\s*(-?[\d.]+) dB", p.stderr)
    if not m:
        return
    gain = ceiling - float(m.group(1))
    tmp = path + ".n.flac"
    ff(["-i", path, "-af", f"volume={gain:.2f}dB", tmp]); os.replace(tmp, path)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("track", help="a .flac in output/ (path or name)")
    ap.add_argument("--crush", choices=["light", "heavy"], default="heavy")
    ap.add_argument("--no-hiss", dest="hiss", action="store_false")
    ap.add_argument("--no-crackle", dest="crackle", action="store_false")
    ap.add_argument("--crackle-thresh", type=float, default=0.22,
                    help="lower = crackle pops more often, higher = rarer/more isolated")
    ap.add_argument("--vocal-gain", type=float, default=0.0, help="extra dB on the lo-fi vocal")
    ap.add_argument("--warble", action="store_true", help="slow tape pitch-drift on the whole mix")
    a = ap.parse_args()

    name = os.path.basename(a.track); base = os.path.splitext(name)[0]
    if not os.path.exists(os.path.join(OUT, name)):
        print(f"not found: output/{name}", file=sys.stderr); sys.exit(1)

    # 1. ensure stems (stems.py separates on CPU — safe for long tracks)
    sdir = os.path.join(OUT, "stems", base)
    if not os.path.exists(os.path.join(sdir, "vocals.wav")):
        print("separating stems first…")
        if subprocess.run(["python3", os.path.join(ROOT, "stems.py"), name]).returncode != 0:
            sys.exit(1)
    stem = lambda s: os.path.join(sdir, s)
    dur = duration(stem("vocals.wav"))

    # 2. lo-fi the vocal
    voc = CRUSH[a.crush] + (f",volume={a.vocal_gain}dB" if a.vocal_gain else "")
    ff(["-i", stem("vocals.wav"), "-af", voc, stem("vocals_lofi.wav")])

    # 3. noise bed: constant hiss + random sparse crackle (crackle gated by a slow random envelope)
    inputs = ["-i", stem("vocals_lofi.wav"), "-i", stem("drums.wav"),
              "-i", stem("bass.wav"), "-i", stem("other.wav")]
    n = 4
    beds = []
    if a.hiss:
        beds.append(f"anoisesrc=d={dur:.2f}:c=white:a=0.010,highpass=f=4000[hiss]")
    if a.crackle:
        beds.append(f"anoisesrc=d={dur:.2f}:c=white:a=0.9,acrusher=samples=140:bits=12:mix=1:mode=lin,"
                    f"highpass=f=1800[crkraw]")
        beds.append(f"anoisesrc=d={dur:.2f}:c=brown:a=1.0,lowpass=f=2,volume=28dB,alimiter=limit=0.99[key]")
        beds.append(f"[crkraw][key]sidechaingate=threshold={a.crackle_thresh}:ratio=30:attack=1:"
                    f"release=50:range=0.002[crk];[crk]volume=1.4[crkv]")
    bed_labels = ([("[hiss]") if a.hiss else ""] + (["[crkv]"] if a.crackle else []))
    bed_labels = [b for b in bed_labels if b]

    parts = list(beds)
    mix_inputs = "[0][1][2][3]"
    if bed_labels:
        parts.append(f"{''.join(bed_labels)}amix=inputs={len(bed_labels)}:normalize=0[bed]")
        mix_inputs += "[bed]"
    final = f"{mix_inputs}amix=inputs={n + (1 if bed_labels else 0)}:duration=first:normalize=0,alimiter=limit=0.95"
    if a.warble:
        final += ",vibrato=f=0.6:d=0.10"
    fc = ";".join(parts + [final + "[out]"]) if parts else final + "[out]"

    out = os.path.join(OUT, f"{base}_lofi.flac")
    ff([*inputs, "-filter_complex", fc, "-map", "[out]", out])
    peak_normalize(out)

    with open(out + ".json", "w") as f:
        json.dump({"tags": f"lo-fi vocal ({a.crush} crush"
                   + (", hiss" if a.hiss else "") + (", random crackle" if a.crackle else "")
                   + (", warble" if a.warble else "") + ")",
                   "source": name, "seconds": round(dur)}, f, indent=2)
    print("->", os.path.relpath(out, ROOT))

if __name__ == "__main__":
    main()
