"""
voice_demo.py — generate side-by-side Hindi voice demo clips (Bulbul V3)
so you can compare candidates before picking one for the channel.

Usage:
    export SARVAM_API_KEY=your_key_here
    python3 agents/voice_demo.py
    python3 agents/voice_demo.py --text "अपना खुद का टेक्स्ट यहाँ डालें"
    python3 agents/voice_demo.py --voices rehan,vijay,simran,kavya

Output: output/voice_demos/<voice_name>.wav — one file per voice tested.
"""

import os
import sys
import base64
import argparse
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()  # reads .env in the current directory (or nearest parent)
except ImportError:
    pass  # falls back to whatever's already in the shell environment

SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY")
API_URL = "https://api.sarvam.ai/text-to-speech"

# Candidates worth testing for an energetic, engaging Hindi narration voice.
# Bulbul V3 has 39 speakers total; this is a shortlist, not the full set —
# pass --voices to override or add more names from Sarvam's speaker list.
DEFAULT_MALE = ["rehan", "vijay", "tarun", "sunny", "mohit", "soham", "shubh"]
DEFAULT_FEMALE = ["simran", "kavya", "ishita", "tanya", "suhani"]

DEFAULT_TEXT = (
    "नमस्ते दोस्तों! आज हम एक बहुत ही दिलचस्प विषय पर बात करने वाले हैं। "
    "अगर आपको यह वीडियो पसंद आए, तो चैनल को सब्सक्राइब करना मत भूलिएगा!"
)

OUT_DIR = "output/voice_demos"


def generate(voice, text, pace=1.15, temperature=0.7):
    if not SARVAM_API_KEY:
        print("ERROR: SARVAM_API_KEY not found in .env or shell environment.")
        sys.exit(1)

    payload = {
        "text": text,
        "target_language_code": "hi-IN",
        "speaker": voice,
        "model": "bulbul:v3",
        "pace": pace,
        "temperature": temperature,
        "enable_preprocessing": True,
    }
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json",
    }

    resp = requests.post(API_URL, json=payload, headers=headers, timeout=60)

    if resp.status_code != 200:
        print(f"  [{voice}] FAILED — {resp.status_code}: {resp.text[:200]}")
        return False

    data = resp.json()
    audio_b64 = data.get("audios", [None])[0]
    if not audio_b64:
        print(f"  [{voice}] FAILED — no audio in response: {data}")
        return False

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{voice}.wav")
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(audio_b64))

    print(f"  [{voice}] saved -> {out_path}")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", default=DEFAULT_TEXT, help="Hindi sample line to test")
    parser.add_argument("--voices", default=None, help="comma-separated voice names, overrides default shortlist")
    parser.add_argument("--pace", type=float, default=1.15)
    parser.add_argument("--temperature", type=float, default=0.7)
    args = parser.parse_args()

    if args.voices:
        voices = [v.strip() for v in args.voices.split(",")]
    else:
        voices = DEFAULT_MALE + DEFAULT_FEMALE

    print(f"Generating {len(voices)} demo clip(s) with pace={args.pace}, temperature={args.temperature}")
    print(f'Sample text: "{args.text}"\n')

    ok, failed = 0, 0
    for v in voices:
        if generate(v, args.text, args.pace, args.temperature):
            ok += 1
        else:
            failed += 1

    print(f"\nDone. {ok} succeeded, {failed} failed.")
    print(f"Play the files in {OUT_DIR}/ — e.g. on mac: afplay {OUT_DIR}/rehan.wav")


if __name__ == "__main__":
    main()
