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
    # Remove timing labels like (0s-5s), (5s-35s)
    script = re.sub(r"\(\d+s-\d+s\)", "", script)
    # Remove labels like Hook:, Main Content:, CTA:
    script = re.sub(r"\b(Hook|Main Content|CTA)\s*:\s*", "", script, flags=re.IGNORECASE)
    # Remove quote marks
    script = script.replace('"', "")
    return script.strip()

def split_into_lines(text, max_words=12):
    # Split on sentence-ending punctuation
    sentences = re.split(r'(?<=[.!?])\s+', text)
    lines = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        words = sentence.split()
        # Further break long sentences into chunks of max_words
        for i in range(0, len(words), max_words):
            chunk = " ".join(words[i:i + max_words])
            lines.append(chunk)

    return lines

def create_srt(script, audio_path="output/voice.mp3"):
    cleaned = clean_script(script)
    lines = split_into_lines(cleaned)

    if not lines:
        lines = [cleaned]

    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    audio.close()

    per_line = total_duration / len(lines)

    srt_content = ""
    start = 0

    for i, line in enumerate(lines):
        end = start + per_line
        srt_content += f"{i+1}\n{format_time(start)} --> {format_time(end)}\n{line}\n\n"
        start = end

    output_file = "output/captions.srt"
    with open(output_file, "w") as f:
        f.write(srt_content)

    return output_file