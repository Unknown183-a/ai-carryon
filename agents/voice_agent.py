import os
import re
from dotenv import load_dotenv
load_dotenv()

MIN_DURATION = 20
MAX_DURATION = 40

def generate_voice(script, output_path="output/voice.mp3"):
    from gtts import gTTS
    from moviepy import AudioFileClip

    os.makedirs("output", exist_ok=True)

    clean = re.sub(r'\(.*?\)', '', script)
    clean = re.sub(r'\*+', '', clean)
    clean = clean.strip()

    tts = gTTS(text=clean, lang='en', slow=False)
    tts.save(output_path)

    # Check duration
    audio = AudioFileClip(output_path)
    duration = audio.duration
    audio.close()

    print(f"Voice duration: {duration:.1f}s")

    if duration > MAX_DURATION:
        print(f"Trimming to {MAX_DURATION}s...")
        audio = AudioFileClip(output_path).subclipped(0, MAX_DURATION)
        audio.write_audiofile(output_path, logger=None)
        audio.close()
        print(f"Trimmed to {MAX_DURATION}s")
    elif duration < MIN_DURATION:
        print(f"Warning: audio is only {duration:.1f}s — script may be too short")

    return output_path
