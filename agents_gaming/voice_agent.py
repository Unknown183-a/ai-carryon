# agents_gaming/voice_agent.py
"""
Gaming V2 Sprint 2 (Phase 6) — a commentator, not a narrator.

Lines are synthesised ONE AT A TIME so the renderer can place each exactly where
it belongs on the clip's timeline (hook up front, setup before the payoff, tag
after it) instead of one continuous voiceover — natural pauses by construction.

The voice style follows the moment (spec §9): hype / funny / calm / dramatic /
rage. Edge-TTS voices only differ in voice, rate and pitch, so a style is a
small preset of those three. If a preset's voice isn't available the line falls
back to the voice that already works in production, then to the shared TTS
(which has its own gTTS fallback) — a line is only dropped if all of that fails.
"""
import asyncio
import os

from agents_gaming.moment_analyzer import probe_duration

FALLBACK_VOICE = "en-US-AndrewMultilingualNeural"   # known-good in the existing pipeline

# base speed ~1.05x (spec: "speed: 1.05, energy: high")
VOICE_PROFILES = {
    "hype":     {"voice": "en-US-GuyNeural",         "rate": "+12%", "pitch": "+2Hz"},
    "funny":    {"voice": FALLBACK_VOICE,            "rate": "+6%",  "pitch": "+0Hz"},
    "calm":     {"voice": "en-US-ChristopherNeural", "rate": "+2%",  "pitch": "-1Hz"},
    "dramatic": {"voice": "en-US-ChristopherNeural", "rate": "-3%",  "pitch": "-2Hz"},
    "rage":     {"voice": "en-US-EricNeural",        "rate": "+14%", "pitch": "+3Hz"},
}

VOICE_STYLE_BY_MOMENT = {
    "CLUTCH": "dramatic", "INSANE_PLAY": "hype", "FAIL": "funny", "FUNNY": "funny",
    "RAGE": "rage", "LUCK": "hype", "UNEXPECTED": "hype", "TROLL": "funny",
    "RECORD": "hype", "DRAMA": "dramatic", "REACTION": "hype",
}


def voice_style_for(moment):
    return VOICE_STYLE_BY_MOMENT.get((moment or {}).get("moment_type", ""), "hype")


async def _edge_save(text, path, voice, rate, pitch):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(path)


def _tts_edge(text, path, profile):
    """Try the style's voice, then the known-good voice. True on success."""
    voices = [(profile["voice"], profile["rate"], profile["pitch"])]
    if profile["voice"] != FALLBACK_VOICE:
        voices.append((FALLBACK_VOICE, profile["rate"], "+0Hz"))
    for voice, rate, pitch in voices:
        try:
            asyncio.run(_edge_save(text, path, voice, rate, pitch))
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return True
        except Exception as e:
            print(f"Voice '{voice}' failed for a line: {e}")
    return False


def _tts_shared(text, path):
    """Last resort: the shared voice agent (edge -> gTTS chain)."""
    try:
        from agents.voice_agent import generate_voice
        generate_voice(text, output_path=path)
        return os.path.exists(path) and os.path.getsize(path) > 0
    except Exception as e:
        print(f"Shared TTS fallback failed: {e}")
        return False


def synth_line(text, path, style="hype"):
    """Synthesise one line. Returns its duration in seconds, or None on failure."""
    text = " ".join(str(text or "").replace("...", ", ").split())
    if not text:
        return None
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    profile = VOICE_PROFILES.get(style, VOICE_PROFILES["hype"])
    ok = _tts_edge(text, path, profile) or _tts_shared(text, path)
    if not ok:
        return None
    dur = probe_duration(path)
    return round(dur, 3) if dur else None


def synth_lines(lines, style, out_dir):
    """lines: [{'kind','text'}] -> same dicts + 'path' + 'duration'. Lines whose
    synthesis fails are omitted (the renderer places what it has)."""
    out = []
    for i, line in enumerate(lines):
        path = os.path.join(out_dir, f"line_{i}_{line['kind']}.mp3")
        dur = synth_line(line["text"], path, style)
        if dur:
            out.append({**line, "path": path, "duration": dur})
        else:
            print(f"Narration line '{line['kind']}' could not be voiced — skipping it")
    return out
