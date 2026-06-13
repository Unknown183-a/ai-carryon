# agents/caption_agent.py
import re
from moviepy import AudioFileClip

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def clean_script(script):
    script = re.sub(r"\(\d+s-\d+s\)", "", script)
    script = re.sub(r"\b(Hook|Main Content|CTA)\s*:\s*", "", script, flags=re.IGNORECASE)
    script = script.replace('"', "")
    return script.strip()

def create_srt(script, audio_path="output/voice.mp3"):
    cleaned = clean_script(script)

    # Split into words
    words = cleaned.split()

    if not words:
        words = [cleaned]

    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    audio.close()

    # Group into chunks of 3 words (Fireship-style)
    chunk_size = 3
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)

    per_chunk = total_duration / len(chunks)

    srt_content = ""
    start = 0

    for i, chunk in enumerate(chunks):
        end = start + per_chunk
        srt_content += f"{i+1}\n{format_time(start)} --> {format_time(end)}\n{chunk}\n\n"
        start = end

    output_file = "output/captions.srt"
    with open(output_file, "w") as f:
        f.write(srt_content)

    return output_file
