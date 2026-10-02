# agents_bhakti/bhakti_voice_agent.py
"""Voice direction + per-scene Hindi TTS + post-processing (spec sections 13-15).

Each scene is voiced separately with direction (pace/temperature/pause) tied
to its story purpose, which also gives *exact* per-scene timings for the
visual edit and captions. Post-processing is pure ffmpeg (no pydub needed).
Falls back to the legacy single-pass voice_agent.generate_voice if per-scene
TTS fails.
"""

import base64
import os
import re
import shutil
import subprocess

SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")
PRIMARY_SPEAKER = os.environ.get("BHAKTI_VOICE_PRIMARY", "vijay")
FALLBACK_SPEAKER = os.environ.get("BHAKTI_VOICE_FALLBACK", "shubh")
WORK_DIR = "output/bhakti_voice"

# purpose -> delivery. pace: <1 slower. temperature: variation. pause: seconds after the scene.
DIRECTION = {
    "hook":       {"emotion": "curious",   "pace": 1.00, "temperature": 0.65, "pause": 0.35},
    "setup":      {"emotion": "warm",      "pace": 0.95, "temperature": 0.55, "pause": 0.30},
    "conflict":   {"emotion": "serious",   "pace": 0.88, "temperature": 0.50, "pause": 0.40},
    "divine":     {"emotion": "reverent",  "pace": 0.86, "temperature": 0.55, "pause": 0.55},
    "resolution": {"emotion": "uplifting", "pace": 0.92, "temperature": 0.50, "pause": 0.35},
    "ending":     {"emotion": "calm",      "pace": 0.88, "temperature": 0.45, "pause": 0.0},
}

# Pronunciation fixes applied only to TTS text (captions keep the original).
PRONUNCIATION = {
    "ॐ": "ओम",
    "श्रीकृष्ण": "श्री कृष्ण",
    "श्रीराम": "श्री राम",
    "हनुमानजी": "हनुमान जी",
    "महादेवजी": "महादेव जी",
    "&": " और ",
}
_DIGITS = {"0": "शून्य", "1": "एक", "2": "दो", "3": "तीन", "4": "चार", "5": "पाँच",
           "6": "छह", "7": "सात", "8": "आठ", "9": "नौ"}


def prepare_tts_text(text):
    t = text.strip()
    for a, b in PRONUNCIATION.items():
        t = t.replace(a, b)
    t = re.sub(r"\d", lambda m: _DIGITS[m.group(0)], t)
    t = re.sub(r"[\"“”*_#]", "", t)
    t = re.sub(r"\s+", " ", t)
    if t and t[-1] not in "।.?!,":
        t += "।"                      # sentence-final marker -> natural falling pause
    return t


def _ffmpeg():
    try:
        from agents.video_agent import get_ffmpeg
        return get_ffmpeg()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr[-400:]}")
    return r


def probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True)
    return float(out.stdout.strip())


def _tts_sarvam(text, out_wav, speaker, pace, temperature):
    from sarvamai import SarvamAI
    client = SarvamAI(api_subscription_key=SARVAM_API_KEY)
    audio = client.text_to_speech.convert(
        text=text[:2500], language_code="hi-IN", speaker=speaker, model="bulbul:v3",
        pace=pace, temperature=temperature)
    parts = []
    for i, b64 in enumerate(audio.audios):
        p = f"{out_wav}.part{i}.wav"
        with open(p, "wb") as f:
            f.write(base64.b64decode(b64))
        parts.append(p)
    if len(parts) == 1:
        shutil.move(parts[0], out_wav)
    else:
        lst = f"{out_wav}.txt"
        with open(lst, "w") as f:
            for p in parts:
                f.write(f"file '{os.path.abspath(p)}'\n")
        _run([_ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out_wav])


def _tts_edge(text, out_path, pace):
    import asyncio
    import edge_tts
    rate = f"{int(round((pace - 1.0) * 100)):+d}%"
    async def _gen():
        await edge_tts.Communicate(text, "hi-IN-MadhurNeural", rate=rate).save(out_path)
    asyncio.run(_gen())


def synthesize_scene(text, out_path, direction, tts_fn=None):
    """Voice one scene -> wav/mp3 at out_path. tts_fn(text,out_path,direction) overrides (tests)."""
    if tts_fn:
        return tts_fn(text, out_path, direction)
    if SARVAM_API_KEY:
        for speaker in (PRIMARY_SPEAKER, FALLBACK_SPEAKER):
            try:
                _tts_sarvam(text, out_path, speaker, direction["pace"], direction["temperature"])
                return out_path
            except Exception as e:
                print(f"[bhakti_voice] Sarvam/{speaker} failed: {e}")
    _tts_edge(text, out_path, direction["pace"])
    return out_path


def trim_silence(src, dst):
    """Remove leading/trailing silence; keep a hair of room so words aren't clipped."""
    _run([_ffmpeg(), "-y", "-i", src, "-af",
          "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
          "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse",
          "-ar", "44100", "-ac", "1", dst])
    return dst


def process_voice(src, dst):
    """EQ + gentle noise reduction + compression + loudness normalisation (+ very light room)."""
    reverb = os.environ.get("BHAKTI_VOICE_REVERB", "1") == "1"
    chain = [
        "highpass=f=80",
        "afftdn=nr=6:nf=-40",
        "equalizer=f=220:t=q:w=1:g=1.5",      # warmth
        "equalizer=f=3200:t=q:w=1:g=2",       # presence / intelligibility
        "acompressor=threshold=-20dB:ratio=3:attack=15:release=200:makeup=3",
    ]
    if reverb:
        chain.append("aecho=0.8:0.9:55:0.10")  # subtle temple-room tail
    chain.append("loudnorm=I=-16:TP=-1.5:LRA=9")
    _run([_ffmpeg(), "-y", "-i", src, "-af", ",".join(chain), "-ar", "44100", "-ac", "1", dst])
    return dst


def generate_scene_voice(scenes, tts_fn=None, work_dir=WORK_DIR):
    """Voice all scenes, fill scene.start/end, return (voice_path, segments).

    Timeline: scene i speech starts at cursor; the scene's *visual* window runs
    from its speech start to the next scene's speech start (so pauses stay on
    the scene that owns them) and the last scene runs to the end of the audio.
    """
    shutil.rmtree(work_dir, ignore_errors=True)
    os.makedirs(work_dir, exist_ok=True)
    ff = _ffmpeg()

    pieces, segments, cursor = [], [], 0.0
    for sc in scenes:
        d = DIRECTION.get(sc.purpose, DIRECTION["setup"])
        raw = os.path.join(work_dir, f"raw_{sc.scene_id}.wav")
        trimmed = os.path.join(work_dir, f"scene_{sc.scene_id}.wav")
        synthesize_scene(prepare_tts_text(sc.narration), raw, d, tts_fn)
        trim_silence(raw, trimmed)
        dur = probe_duration(trimmed)
        pieces.append(trimmed)
        segments.append({"scene_id": sc.scene_id, "start": round(cursor, 3),
                         "end": round(cursor + dur, 3), "path": trimmed,
                         "emotion": d["emotion"]})
        cursor += dur
        if d["pause"] > 0 and sc is not scenes[-1]:
            gap = os.path.join(work_dir, f"gap_{sc.scene_id}.wav")
            _run([ff, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                  "-t", f"{d['pause']:.2f}", gap])
            pieces.append(gap)
            cursor += d["pause"]

    lst = os.path.join(work_dir, "concat.txt")
    with open(lst, "w") as f:
        for p in pieces:
            f.write(f"file '{os.path.abspath(p)}'\n")
    joined = os.path.join(work_dir, "joined.wav")
    _run([ff, "-y", "-f", "concat", "-safe", "0", "-i", lst, "-ar", "44100", "-ac", "1", joined])

    os.makedirs("output", exist_ok=True)
    final = "output/voice.mp3"
    processed = os.path.join(work_dir, "processed.wav")
    process_voice(joined, processed)
    _run([ff, "-y", "-i", processed, "-c:a", "libmp3lame", "-b:a", "192k", final])
    total = probe_duration(final)

    # Visual windows: each scene spans from its speech start to the next scene's start.
    for i, sc in enumerate(scenes):
        sc.start = 0.0 if i == 0 else segments[i]["start"]
        sc.end = segments[i + 1]["start"] if i + 1 < len(segments) else total
        segments[i]["scene_start"], segments[i]["scene_end"] = sc.start, sc.end
    return final, segments


def generate_bhakti_voice(scenes, script, tts_fn=None):
    """Public entry: per-scene voice, falling back to the legacy single pass.

    Returns (voice_path, segments). With the legacy fallback, segments is []
    and scene timings are distributed proportionally to word counts."""
    try:
        return generate_scene_voice(scenes, tts_fn=tts_fn)
    except Exception as e:
        print(f"[bhakti_voice] per-scene voice failed ({e}) — legacy single-pass voice")
        from agents_bhakti.voice_agent import generate_voice
        path = generate_voice(script)
        total = probe_duration(path)
        words = [max(len(s.narration.split()), 1) for s in scenes]
        t, cursor = float(sum(words)), 0.0
        for sc, w in zip(scenes, words):
            sc.start, sc.end = cursor, cursor + total * w / t
            cursor = sc.end
        return path, []
