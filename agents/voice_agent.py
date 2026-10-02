import os
import re
import asyncio
import subprocess
from dotenv import load_dotenv
load_dotenv()

MIN_DURATION = 20
MAX_DURATION = 58      # YouTube Shorts limit is 60s — leave a little headroom
MAX_SPEEDUP = 1.25     # never speed speech up more than this (stays natural)

async def _generate_edge_tts(text, output_path, voice):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate="+10%")
    await communicate.save(output_path)

def _ffmpeg_audio(src, dst, *filters, extra=()):
    cmd = ["ffmpeg", "-y", "-i", src, *extra]
    if filters:
        cmd += ["-filter:a", ",".join(filters)]
    cmd.append(dst)
    subprocess.run(cmd, check=True, capture_output=True)


def _fit_to_max_duration(path, duration):
    """Make the voiceover fit MAX_DURATION without chopping words.

    1) Speed up slightly (atempo, capped at MAX_SPEEDUP) — speech stays
       complete and natural.
    2) Only if that is still not enough, cut with a short fade-out so it
       never ends in a harsh mid-word chop (and log it loudly).
    """
    base, ext = os.path.splitext(path)
    tmp = f"{base}.tmp{ext}"

    factor = min(duration / (MAX_DURATION - 0.5), MAX_SPEEDUP)
    print(f"Voice {duration:.1f}s > {MAX_DURATION}s — speeding up x{factor:.3f} instead of cutting")
    _ffmpeg_audio(path, tmp, f"atempo={factor:.4f}")
    os.replace(tmp, path)

    from moviepy import AudioFileClip
    clip = AudioFileClip(path)
    new_duration = clip.duration
    clip.close()
    print(f"Voice duration after speed-up: {new_duration:.1f}s")

    if new_duration > MAX_DURATION:
        print(f"WARNING: still over {MAX_DURATION}s — last-resort trim with fade-out. "
              f"Script is too long; shorten it.")
        _ffmpeg_audio(path, tmp, f"afade=t=out:st={MAX_DURATION - 0.6}:d=0.6",
                      extra=("-t", str(MAX_DURATION)))
        os.replace(tmp, path)
    return path


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
        output_path = _fit_to_max_duration(output_path, duration)

    return output_path
