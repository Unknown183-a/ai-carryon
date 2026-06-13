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
    words = cleaned.split()

    if not words:
        words = [cleaned]

    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    audio.close()

    # Time per word
    per_word = total_duration / len(words)

    # Group into chunks of 4 words, track which word is "current"
    chunk_size = 4
    entries = []
    
    for i in range(0, len(words), chunk_size):
        chunk_words = words[i:i + chunk_size]
        chunk_start = i * per_word
        
        # For each word in chunk, create an entry showing
        # the full chunk with that word highlighted
        for j, current_word in enumerate(chunk_words):
            word_start = (i + j) * per_word
            word_end = (i + j + 1) * per_word
            
            # Build display: before | CURRENT | after
            before = " ".join(chunk_words[:j])
            after = " ".join(chunk_words[j+1:])
            
            entries.append({
                "start": word_start,
                "end": word_end,
                "before": before,
                "current": current_word,
                "after": after
            })

    # Save word-level data as JSON for video_agent to use
    import json
    with open("output/captions_words.json", "w") as f:
        json.dump(entries, f)

    # Also save standard SRT as fallback
    srt_content = ""
    chunk_size = 3
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i+chunk_size]))
    
    per_chunk = total_duration / len(chunks)
    start = 0
    for i, chunk in enumerate(chunks):
        end = start + per_chunk
        srt_content += f"{i+1}\n{format_time(start)} --> {format_time(end)}\n{chunk}\n\n"
        start = end

    with open("output/captions.srt", "w") as f:
        f.write(srt_content)

    return "output/captions.srt"
