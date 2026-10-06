# agents_gaming/transcript_agent.py
"""
Gaming V2 Sprint 2 — hear the clip.

The commentary writer used to work from 5 silent frames and a title, so it
invented chat reactions and generic hype. A Twitch clip's audio carries what
actually happened: the streamer's words, the reaction, the catchphrase. This
agent transcribes it with Groq's Whisper endpoint (its own rate limit, not the
LLM token budget and not the Gemini quota) and feeds the text to the moment
analyzer, hook and commentary agents.

Whisper hallucinates on silence/music ("Thanks for watching!"), and gameplay
is mostly noise, so segments are filtered hard. Everything here degrades to
`None` — a transcript is an enhancement, never a requirement. Never raises.
"""
import os
import subprocess
import tempfile

from agents_gaming.audio_peak import ffmpeg_bin, has_audio_stream

WHISPER_MODEL = os.getenv("GAMING_WHISPER_MODEL", "whisper-large-v3-turbo")
TRANSCRIBE_ENABLED = os.getenv("GAMING_TRANSCRIBE", "1") != "0"
MAX_NO_SPEECH_PROB = 0.6
MIN_AVG_LOGPROB = -1.0
MIN_WORDS = 3
MAX_TRANSCRIPT_CHARS = 700

# Classic Whisper hallucinations on non-speech audio.
_HALLUCINATIONS = (
    "thanks for watching", "thank you for watching", "subscribe", "like and subscribe",
    "see you in the next", "please subscribe", "www.", "subtitles by", "amara.org",
    "transcription by",
)


def extract_audio(video_path, out_path=None):
    """Mono 16 kHz FLAC of the clip's audio (small, Whisper-friendly). None on failure."""
    if not video_path or not os.path.exists(video_path) or not has_audio_stream(video_path):
        return None
    out_path = out_path or os.path.join(tempfile.mkdtemp(prefix="gaming_audio_"), "audio.flac")
    r = subprocess.run(
        [ffmpeg_bin(), "-y", "-v", "error", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "flac", out_path],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        return None
    return out_path


def _as_dict(resp):
    if isinstance(resp, dict):
        return resp
    for attr in ("model_dump", "dict"):
        fn = getattr(resp, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass
    return {k: getattr(resp, k) for k in ("text", "language", "segments") if hasattr(resp, k)}


def _is_hallucination(text):
    low = text.lower()
    return any(h in low for h in _HALLUCINATIONS)


def clean_segments(segments):
    """Drop segments Whisper itself flags as non-speech / low confidence, and
    known hallucination phrases. Returns [{'start','end','text'}]."""
    out = []
    for s in segments or []:
        if not isinstance(s, dict):
            continue
        text = str(s.get("text", "")).strip()
        if not text or _is_hallucination(text):
            continue
        if float(s.get("no_speech_prob", 0) or 0) > MAX_NO_SPEECH_PROB:
            continue
        if float(s.get("avg_logprob", 0) or 0) < MIN_AVG_LOGPROB:
            continue
        out.append({"start": round(float(s.get("start", 0) or 0), 2),
                    "end": round(float(s.get("end", 0) or 0), 2), "text": text})
    return out


def transcribe_clip(video_path, client=None):
    """Returns {'text','language','segments','words'} or None when the clip has
    no usable speech (or anything fails). `client` is injectable for tests."""
    if not TRANSCRIBE_ENABLED:
        return None
    audio = None
    try:
        audio = extract_audio(video_path)
        if not audio:
            return None
        if client is None:
            from groq import Groq
            key = os.getenv("GROQ_API_KEY")
            if not key:
                return None
            client = Groq(api_key=key)
        with open(audio, "rb") as f:
            resp = client.audio.transcriptions.create(
                file=(os.path.basename(audio), f.read()),
                model=WHISPER_MODEL,
                response_format="verbose_json",
                temperature=0.0,
            )
        data = _as_dict(resp)
        segments = clean_segments(data.get("segments"))
        text = " ".join(s["text"] for s in segments).strip()
        words = len(text.split())
        if words < MIN_WORDS:
            print(f"Transcript: no clear speech ({words} words) — continuing without one")
            return None
        result = {"text": text[:MAX_TRANSCRIPT_CHARS], "language": data.get("language") or "",
                  "segments": segments, "words": words}
        print(f"Transcript: {words} words, language={result['language'] or '?'}")
        return result
    except Exception as e:
        print(f"Transcript skipped: {e}")
        return None
    finally:
        if audio:
            try:
                os.remove(audio)
            except OSError:
                pass


def speech_share(transcript, duration):
    """Fraction of the clip (0-1) the streamer is talking. Used to keep the
    narration out of the way when the clip's own audio is the content."""
    if not transcript or not duration:
        return 0.0
    spoken = sum(max(s["end"] - s["start"], 0) for s in transcript.get("segments", []))
    return max(0.0, min(spoken / float(duration), 1.0))
