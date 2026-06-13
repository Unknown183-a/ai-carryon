# agents/voice_agent.py
import os
from dotenv import load_dotenv
load_dotenv()


def generate_voice(script, output_path="output/voice.mp3"):
    from gtts import gTTS
    
    os.makedirs("output", exist_ok=True)
    
    # Clean script for TTS
    import re
    clean = re.sub(r'\(.*?\)', '', script)
    clean = re.sub(r'\*+', '', clean)
    clean = clean.strip()
    
    tts = gTTS(text=clean, lang='en', slow=False)
    tts.save(output_path)
    
    print(f"Voice saved: {output_path}")
    return output_path
