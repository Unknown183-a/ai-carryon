# agents/voice_agent.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # Adam - energetic tech voice

def generate_voice(script):
    os.makedirs("output", exist_ok=True)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "text": script,
        "model_id": "eleven_turbo_v2",
        "voice_settings": {
            "stability": 0.4,
            "similarity_boost": 0.8,
            "style": 0.5,
            "use_speaker_boost": True
        }
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    output_path = "output/voice.mp3"
    with open(output_path, "wb") as f:
        f.write(response.content)

    return output_path
