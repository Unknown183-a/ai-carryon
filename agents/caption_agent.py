# agents/caption_agent.py
import re
from dotenv import load_dotenv
load_dotenv()


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


def split_into_words(text):
    """Split text into individual words, keeping punctuation attached"""
    words = text.split()
    return [w for w in words if w.strip()]


def create_srt(script, audio_path="output/voice.mp3"):
    from moviepy import AudioFileClip

    cleaned = clean_script(script)
    words = split_into_words(cleaned)

    if not words:
        words = [cleaned]

    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    audio.close()

    # Average seconds per word
    per_word = total_duration / len(words)

    srt_content = ""
    start = 0

    for i, word in enumerate(words):
        end = start + per_word
        srt_content += f"{i+1}\n{format_time(start)} --> {format_time(end)}\n{word}\n\n"
        start = end

    output_file = "output/captions.srt"
    with open(output_file, "w") as f:
        f.write(srt_content)

    return output_file


def get_word_timings(script, audio_path="output/voice.mp3"):
    """Returns list of (word, start, end) tuples"""
    from moviepy import AudioFileClip

    cleaned = clean_script(script)
    words = split_into_words(cleaned)

    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    audio.close()

    per_word = total_duration / len(words)
    timings = []
    start = 0

    for word in words:
        end = start + per_word
        timings.append((word, start, end))
        start = end

    return timings