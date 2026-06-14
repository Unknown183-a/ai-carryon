import os
import re
import asyncio
from dotenv import load_dotenv
load_dotenv()

MIN_DURATION = 20
MAX_DURATION = 40

async def _generate_edge_tts(text, output_path, voice):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate="+10%")
    await communicate.save(output_path)

def generate_voice(script, output_path="output/voice.mp3"):
    from moviepy import AudioFileClip

    os.makedirs("output", exist_ok=True)

    clean = re.sub(r'\(.*?\)', '', script)
    clean = re.sub(r'\*+', '', clean)
    clean = re.sub(r'[#@]', '', clean)
    clean = clean.strip()

    # Best human-sounding voices - try in order
    voices = [
        "en-US-AndrewMultilingualNeural",   # best male
        "en-US-AvaMultilingualNeural",       # best female
        "en-US-GuyNeural",                   # male fallback
        "en-US-JennyNeural",                 # female fallback
    ]

    success = False
    for voice in voices:
        try:
            print(f"Trying voice: {voice}")
            asyncio.run(_generate_edge_tts(clean, output_path, voice))
            success = True
            print(f"Voice generated with: {voice}")
            break
        except Exception as e:
            print(f"Voice {voice} failed: {e}")
            continue

    if not success:
        print("All Edge TTS voices failed, falling back to gTTS...")
        from gtts import gTTS
        tts = gTTS(text=clean, lang='en', slow=False)
        tts.save(output_path)

    # Check and trim duration
    audio = AudioFileClip(output_path)
    duration = audio.duration
    audio.close()
    print(f"Voice duration: {duration:.1f}s")

    if duration > MAX_DURATION:
        print(f"Trimming to {MAX_DURATION}s...")
        audio = AudioFileClip(output_path).subclipped(0, MAX_DURATION)
        audio.write_audiofile(output_path, logger=None)
        audio.close()

    return output_path
