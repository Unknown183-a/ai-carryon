# agents_gaming/gameplay_hook.py
"""
Gaming hook: a cold open cut from the ORIGINAL gameplay (spec §16, priority 1).

    clip + moment analysis -> peak moment (key_timestamp) -> 1-2s cut -> opens the Short
                           -> the full clip then plays from the start (setup -> payoff)

Why not Pexels here: stock footage over a real Twitch highlight would be a
different subject by definition, so the relevance gate could never be honestly
met. Relevance is 1.0 by construction (same footage); no Pexels key is needed.

Conservative on purpose. The moment analyzer samples only 5 frames, so
key_timestamp is approximate; we only cut when the analysis came from the
vision tier and the moment is intense. Otherwise returns None and the clip
renders exactly as before ("no suitable hook -> strongest main clip", spec §20).
"""
import os

from agents.hook_engine import MIN_HOOK_SEC, MAX_HOOK_SEC, _clamp

MIN_INTENSITY = int(os.getenv("GAMING_HOOK_MIN_INTENSITY", "6"))
MIN_CLIP_SECONDS = 6.0          # shorter clips are all hook already
ALREADY_OPENS_ON_ACTION = 3.0   # payoff within the first 3s -> no cold open needed

# Fast moments get a short cut, slower story-like ones a bit more room (spec §12).
_DURATION_BY_MOMENT = {
    "CLUTCH": 1.5, "INSANE_PLAY": 1.2, "FAIL": 1.5, "FUNNY": 2.0, "RAGE": 1.5,
    "LUCK": 1.5, "UNEXPECTED": 1.5, "TROLL": 2.0, "RECORD": 1.5, "DRAMA": 2.5, "REACTION": 2.0,
}
_HOOK_TYPE_BY_MOMENT = {
    "CLUTCH": "action", "INSANE_PLAY": "action", "RAGE": "shock", "FAIL": "shock",
    "UNEXPECTED": "shock", "LUCK": "shock", "RECORD": "shock", "FUNNY": "curiosity",
    "TROLL": "curiosity", "DRAMA": "mystery", "REACTION": "emotional",
}


def _probe(path):
    try:
        from agents_gaming.moment_analyzer import probe_duration
        return probe_duration(path)
    except Exception:
        return None


def select_gameplay_hook(clip_path, moment, clip=None):
    """Return a hook dict for the shared renderer, or None. Never raises."""
    try:
        if not clip_path or not os.path.exists(clip_path) or not moment:
            return None
        if os.getenv("HOOK_ENGINE", "1").strip() == "0" or \
                os.getenv("HOOK_ENGINE_GAMING", "1").strip() == "0":
            return None
        if moment.get("source") != "vision":
            print(f"[hook] gaming: moment came from '{moment.get('source')}' tier, "
                  f"peak time unreliable - no cold open")
            return None
        intensity = int(moment.get("intensity") or 0)
        if intensity < MIN_INTENSITY:
            print(f"[hook] gaming: intensity {intensity} < {MIN_INTENSITY} - no cold open")
            return None

        total = _probe(clip_path) or float((clip or {}).get("duration") or 0)
        if total < MIN_CLIP_SECONDS:
            return None
        key = float(moment.get("key_timestamp") or 0)
        if key <= ALREADY_OPENS_ON_ACTION:
            print("[hook] gaming: clip already opens on the payoff - no cold open")
            return None

        mtype = moment.get("moment_type", "UNEXPECTED")
        dur = round(_clamp(_DURATION_BY_MOMENT.get(mtype, 1.5), MIN_HOOK_SEC, MAX_HOOK_SEC), 2)
        start = max(key - dur * 0.7, 0.0)          # land the payoff ~70% through the cut
        start = min(start, max(total - dur, 0.0))  # never run past the end of the clip
        if start + dur > total + 0.01:
            return None

        hook = {
            "provider": "gameplay", "clip_id": str((clip or {}).get("id", "")), "path": clip_path,
            "start": round(start, 2), "duration": dur,
            "hook_type": _HOOK_TYPE_BY_MOMENT.get(mtype, "shock"),
            "query": "", "title": str(moment.get("what_happened", ""))[:120],
            "relevance": 1.0, "visual_score": round(intensity / 10.0, 2),
            "curiosity_score": 0.0, "emotional_score": 0.0, "continuity_score": 1.0,
            "final_score": round(intensity / 10.0, 2), "scorer": "source",
            "topic": (clip or {}).get("title", ""), "channel": "gaming",
            "selection_reason": (f"peak of the real gameplay: {mtype} intensity {intensity}, "
                                 f"cut {start:.1f}s-{start + dur:.1f}s of {total:.1f}s"),
        }
        print(f"[hook] gaming cold open: {hook['selection_reason']}")
        return hook
    except Exception as e:
        print(f"[hook] gaming hook error (continuing without hook): {e}")
        return None
