#!/usr/bin/env python3
"""Keep up with newer local music models. Read-only: asks the Hugging Face API
what's new among ACE-Step / open music-generation models, and flags which tracked
ones are installed. Prints a report only.

Usage:  python3 check_updates.py
"""
import glob, json, os, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(ROOT, "models")

TRACKED = [
    ("Comfy-Org/ace_step_1.5_ComfyUI_files", "ACE-Step 1.5 (in use)", "checkpoints/ace_step_1.5*"),
    ("ACE-Step/Ace-Step1.5",                 "ACE-Step 1.5 (upstream)", ""),
]
AUTHORS = ["ACE-Step", "Comfy-Org", "ryanontheinside", "QuantStack"]
KEYWORDS = ("ace-step", "ace_step", "acestep", "music", "diffrhythm", "yue", "songgen",
            "muse", "audio")

def hf(url):
    req = urllib.request.Request(url, headers={"User-Agent": "audio-studio-check"})
    return json.load(urllib.request.urlopen(req, timeout=25))

def installed(hint):
    return bool(hint and glob.glob(os.path.join(MODELS_DIR, hint)))

def main():
    print("== Tracked ==")
    for repo, label, hint in TRACKED:
        try:
            m = hf(f"https://huggingface.co/api/models/{repo}")
            lm = (m.get("lastModified") or "?")[:10]
            have = "INSTALLED" if installed(hint) else "-"
            print(f"  {label:26} {repo:38} updated {lm}  [{have}]")
        except Exception as e:
            print(f"  {label:26} {repo:38} ERROR: {e}")

    print("\n== Recently-updated music models (tracked authors) ==")
    seen = set()
    for author in AUTHORS:
        try:
            lst = hf(f"https://huggingface.co/api/models?author={author}"
                     "&sort=lastModified&direction=-1&limit=25")
        except Exception as e:
            print(f"  {author}: ERROR {e}"); continue
        shown = 0
        for m in lst:
            rid = m.get("id") or m.get("modelId") or ""
            low = rid.lower()
            if not any(k in low for k in KEYWORDS) or rid in seen:
                continue
            seen.add(rid)
            print(f"  [{author}] {(m.get('lastModified') or '')[:10]}  {rid}")
            shown += 1
            if shown >= 6:
                break

if __name__ == "__main__":
    main()
