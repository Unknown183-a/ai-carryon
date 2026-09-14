# agents/caption_agent.py
import re
from moviepy import AudioFileClip

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def _ass_time(seconds):
    """ASS timestamp format: H:MM:SS.CC (centiseconds, 2 digits)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"

def _ass_escape(text):
    return text.replace("\\", "").replace("{", "").replace("}", "")

# Word-highlight ("aesthetic"/karaoke-style) caption look: current word pops
# in a bright accent color while the rest of the chunk stays white, mirroring
# the burned-in caption style already used on the static-image render path
# (draw_caption in agents/video_agent.py — same yellow, same ~65%-down
# position) so all three channels share one visual caption identity
# regardless of which background renderer (static image vs Pexels clip) ends
# up being used for a given run.
_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans Bold,78,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,4,0,2,60,60,650,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def build_ass_captions(entries, output_path="output/captions.ass"):
    """Builds a karaoke-style .ass file from create_srt()'s per-word entries
    (each with start/end/before/current/after). One Dialogue line per word so
    the highlighted word advances in sync with the voiceover, giving the
    "aesthetic" pop-style caption look instead of a static block of subtitle
    text sitting on screen for several seconds."""
    lines = [_ASS_HEADER]
    highlight = "&H00DCFF&"  # BGR yellow — matches draw_caption's (255,220,0)
    base = "&H00FFFFFF&"     # white
    for e in entries:
        before = _ass_escape(e["before"].upper())
        current = _ass_escape(e["current"].upper())
        after = _ass_escape(e["after"].upper())
        parts = []
        if before:
            parts.append(f"{{\\c{base}}}{before} ")
        parts.append(f"{{\\c{highlight}\\fscx112\\fscy112}}{current}{{\\fscx100\\fscy100}}")
        if after:
            parts.append(f"{{\\c{base}}} {after}")
        text = "".join(parts)
        lines.append(
            f"Dialogue: 0,{_ass_time(e['start'])},{_ass_time(e['end'])},Caption,,0,0,0,,{text}"
        )
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    return output_path

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

    # Aesthetic word-highlight captions (used by the Pexels-clip video path,
    # and by any static-image path that goes through burn_captions()).
    build_ass_captions(entries)

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
