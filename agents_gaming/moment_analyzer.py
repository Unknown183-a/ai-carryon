# agents_gaming/moment_analyzer.py
"""
Gaming V2 Phase 2 — understand what actually happened in the clip.

    clip -> extract key frames (ffmpeg) -> vision model -> structured moment

Fallback chain, so a vision outage never stops the channel:
    vision (Gemini, frames + metadata)  ->  text-only LLM (metadata)  ->  title heuristic
The returned dict always has the same shape and a `source` field saying
which tier produced it. This function never raises.

Limitation: frames only — the streamer's voice/game audio isn't heard, so a
moment that is mostly spoken (a funny line, a rage rant) is judged from the
visuals + title. Adding a transcript is a natural later upgrade.
"""
import base64
import os
import re
import subprocess
import tempfile

from agents_gaming.v2_utils import clamp, extract_json

MOMENT_TYPES = [
    "CLUTCH", "FAIL", "FUNNY", "RAGE", "INSANE_PLAY", "LUCK",
    "UNEXPECTED", "TROLL", "RECORD", "DRAMA", "REACTION",
]

VISION_MODEL = os.getenv("GAMING_VISION_MODEL", "gemini-3.5-flash")
VISION_TIMEOUT_SECONDS = int(os.getenv("GAMING_VISION_TIMEOUT_SECONDS", "60"))
FRAME_COUNT = int(os.getenv("GAMING_ANALYZE_FRAMES", "5"))


def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def probe_duration(video_path):
    """Duration in seconds, parsed from ffmpeg's banner (no ffprobe needed)."""
    r = subprocess.run([_ffmpeg(), "-i", video_path], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr or "")
    if not m:
        return None
    h, mnt, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mnt * 60 + s


def extract_frames(video_path, n=FRAME_COUNT, out_dir=None, width=640):
    """Evenly spaced frames from 8% to 92% of the clip. Returns a list of
    (timestamp_seconds, jpg_path); frames that fail to extract are skipped."""
    duration = probe_duration(video_path)
    if not duration or duration <= 0:
        return []
    out_dir = out_dir or tempfile.mkdtemp(prefix="gaming_frames_")
    frames = []
    for i in range(n):
        frac = 0.08 + (0.84 * i / max(n - 1, 1))
        ts = round(duration * frac, 2)
        out = os.path.join(out_dir, f"frame_{i}.jpg")
        r = subprocess.run(
            [_ffmpeg(), "-y", "-ss", str(ts), "-i", video_path, "-frames:v", "1",
             "-vf", f"scale={width}:-2", "-q:v", "4", out],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 0:
            frames.append((ts, out))
    return frames


_SCHEMA = """{
  "game": "<game name>",
  "is_gameplay": <true if the frames show actual video-game footage; false for IRL/webcam-only/just-chatting/menu/lobby footage>,
  "moment_type": "<one of: %s>",
  "what_happened": "<1-2 plain sentences, only what is visible/stated>",
  "setup": "<what led into it>",
  "payoff": "<the outcome>",
  "reaction": "<how the streamer/chat/situation reacts, or 'none visible'>",
  "key_timestamp": <seconds into the clip where the payoff lands>,
  "intensity": <1-10>,
  "funny_score": <0-10>,
  "clutch_score": <0-10>
}""" % ", ".join(MOMENT_TYPES)


def _metadata_block(clip):
    block = (
        f"Clip title: {clip.get('title', '')}\n"
        f"Streamer: {clip.get('broadcaster_name', '')}\n"
        f"Game (if known): {clip.get('_source_game', '') or 'unknown — read it from the frames'}\n"
        f"Clip length: {clip.get('duration', '?')}s"
    )
    if clip.get("_transcript_text"):
        # Sprint 2: what is actually SAID in the clip (auto-transcript, may contain errors).
        block += f"\nStreamer speech (auto-transcribed, may contain errors): {clip['_transcript_text']}"
    return block


def _vision_call(frames, clip):
    from langchain_core.messages import HumanMessage
    from langchain_google_genai import ChatGoogleGenerativeAI

    stamps = ", ".join(f"frame {i + 1} = {ts}s" for i, (ts, _) in enumerate(frames))
    prompt = (
        "You are analysing a short Twitch gaming clip for a YouTube Shorts editor.\n"
        f"{_metadata_block(clip)}\n"
        f"You are given {len(frames)} frames in order ({stamps}).\n\n"
        "Work out what actually happens. Use ONLY what you can see or what the title states — "
        "do not invent scores, kill counts, names or numbers.\n"
        f"Reply with ONLY this JSON object:\n{_SCHEMA}"
    )
    content = [{"type": "text", "text": prompt}]
    for _, path in frames:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    llm = ChatGoogleGenerativeAI(model=VISION_MODEL, google_api_key=os.getenv("GEMINI_API_KEY"))
    return llm.invoke([HumanMessage(content=content)])


def _text_call(clip):
    from agents.model_invoke_agent_english import safe_invoke
    prompt = (
        "You are analysing a Twitch gaming clip from its metadata only (no video).\n"
        f"{_metadata_block(clip)}\n\n"
        "Infer the most likely moment from the title. Do not invent numbers or names not in the title.\n"
        f"Reply with ONLY this JSON object:\n{_SCHEMA}"
    )
    return safe_invoke(prompt)


def heuristic_moment(clip):
    """Last-resort classification from the title alone. Deliberately bland and
    low-intensity so a heuristic moment never wins on its own merits."""
    title = (clip.get("title") or "").lower()
    rules = [
        ("CLUTCH", ("clutch", "1v", "1hp", "1 hp", "one hp", "ace", "survive")),
        ("FAIL", ("fail", "oops", "whiff", "missed", "ruined", "lost")),
        ("RAGE", ("rage", "angry", "mad", "tilt", "furious")),
        ("FUNNY", ("lol", "funny", "haha", "joke", "bro")),
        ("RECORD", ("record", "first", "new high", "world")),
        ("LUCK", ("lucky", "luck", "rng")),
        ("TROLL", ("troll", "prank", "bait")),
        ("INSANE_PLAY", ("insane", "crazy", "unreal", "sick", "cracked")),
    ]
    mtype = "UNEXPECTED"
    for name, keys in rules:
        if any(k in title for k in keys):
            mtype = name
            break
    dur = float(clip.get("duration") or 20)
    return {
        "game": clip.get("_source_game", "") or "",
        "is_gameplay": True,   # can't tell from a title; only vision can say otherwise
        "moment_type": mtype,
        "what_happened": clip.get("title", "").strip(),
        "setup": "",
        "payoff": "",
        "reaction": "none visible",
        "key_timestamp": round(dur * 0.7, 1),
        "intensity": 5,
        "funny_score": 5 if mtype in ("FUNNY", "FAIL", "TROLL") else 2,
        "clutch_score": 5 if mtype in ("CLUTCH", "INSANE_PLAY") else 2,
    }


def _as_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "yes", "1"):
            return True
        if v in ("false", "no", "0"):
            return False
    return default


def normalize_moment(raw, clip, duration=None):
    """Validate/clamp an LLM-produced dict into the canonical moment shape.
    Returns None if it is unusable (so the caller falls to the next tier)."""
    if not isinstance(raw, dict):
        return None
    mtype = str(raw.get("moment_type", "")).strip().upper().replace(" ", "_")
    if mtype not in MOMENT_TYPES:
        return None
    what = str(raw.get("what_happened", "")).strip()
    if not what:
        return None
    dur = duration or float(clip.get("duration") or 0) or None
    key_ts = clamp(raw.get("key_timestamp"), 0, dur if dur else 600, default=(dur or 20) * 0.7)
    return {
        "game": str(raw.get("game") or clip.get("_source_game") or "").strip(),
        "is_gameplay": _as_bool(raw.get("is_gameplay"), default=True),
        "moment_type": mtype,
        "what_happened": what,
        "setup": str(raw.get("setup", "")).strip(),
        "payoff": str(raw.get("payoff", "")).strip(),
        "reaction": str(raw.get("reaction", "")).strip() or "none visible",
        "key_timestamp": round(key_ts, 1),
        "intensity": int(round(clamp(raw.get("intensity"), 1, 10, default=5))),
        "funny_score": int(round(clamp(raw.get("funny_score"), 0, 10, default=0))),
        "clutch_score": int(round(clamp(raw.get("clutch_score"), 0, 10, default=0))),
    }


def analyze_moment(clip, video_path=None):
    """Always returns a moment dict (see _SCHEMA) plus `source`:
    'vision' | 'text' | 'heuristic'. Never raises."""
    duration = None

    if video_path and os.path.exists(video_path):
        try:
            duration = probe_duration(video_path)
            frames = extract_frames(video_path)
            if frames:
                try:
                    from agents.model_invoke_agent_english import _run_with_timeout
                    resp, err = _run_with_timeout(lambda: _vision_call(frames, clip), VISION_TIMEOUT_SECONDS)
                except ImportError:
                    resp, err = _vision_call(frames, clip), None
                if resp is not None:
                    moment = normalize_moment(extract_json(_content_text(resp)), clip, duration)
                    if moment:
                        moment["source"] = "vision"
                        return moment
                print(f"Moment analyzer: vision tier failed ({err or 'unparseable reply'}) — trying text")
            else:
                print("Moment analyzer: no frames extracted — trying text")
        except Exception as e:
            print(f"Moment analyzer: vision tier error: {e} — trying text")

    try:
        resp = _text_call(clip)
        moment = normalize_moment(extract_json(_content_text(resp)), clip, duration)
        if moment:
            moment["source"] = "text"
            return moment
    except Exception as e:
        print(f"Moment analyzer: text tier error: {e} — using heuristic")

    moment = heuristic_moment(clip)
    moment["source"] = "heuristic"
    return moment


def _content_text(resp):
    content = getattr(resp, "content", resp)
    if isinstance(content, list):
        return "".join(p if isinstance(p, str) else (p.get("text") or "") for p in content)
    return str(content or "")
