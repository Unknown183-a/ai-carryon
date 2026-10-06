# agents_gaming/editor_agent.py
"""
Gaming V2 Sprint 2 (Phase 8 + Phase 10) — decide WHAT the edit does, and WHERE
each narration line goes. Deterministic (no LLM, no API quota).

Spec rules this implements:
  - "Do not add effects randomly. Every effect should support the story."
      -> effects only when the payoff time is trustworthy (vision-analysed AND
         intense); a mistimed zoom/freeze looks like a bug, so no trustworthy
         timestamp means NO effects.
  - "Do not narrate continuously."
      -> narration lines are placed on the clip's timeline around the payoff,
         never over it, never over the streamer's own speech if avoidable, and
         dropped (not squeezed) when they don't fit.

All times here are in MAIN-CLIP time (seconds from the start of the clip). The
renderer maps them to the output timeline (cold open / freeze / end hold).
"""

FREEZE_TYPES = {"CLUTCH", "INSANE_PLAY", "FAIL", "UNEXPECTED", "LUCK", "RECORD"}
MIN_KEY, END_MARGIN = 1.2, 0.7
HOOK_START = 0.25
PAYOFF_PRE, PAYOFF_POST = 0.4, 1.0      # protected window around the payoff
LINE_GAP = 0.4
END_HOLD_MAX = 1.5


def plan_edit(moment, clip_duration):
    """-> {'key','zoom','freeze','reasons'}; zoom/freeze are None when not warranted."""
    plan = {"key": None, "zoom": None, "freeze": None, "reasons": []}
    m = moment or {}
    try:
        key = float(m.get("key_timestamp"))
    except (TypeError, ValueError):
        key = None
    d = float(clip_duration or 0)
    if m.get("source") != "vision":
        plan["reasons"].append(f"no effects: moment from '{m.get('source')}' tier, payoff time unreliable")
        return plan
    if key is None or d <= 0 or not (MIN_KEY <= key <= d - END_MARGIN):
        plan["reasons"].append("no effects: payoff time outside the usable part of the clip")
        return plan
    plan["key"] = round(key, 2)

    intensity = int(m.get("intensity") or 0)
    if intensity < 6:
        plan["reasons"].append(f"no effects: intensity {intensity} < 6")
        return plan

    freeze = None
    if intensity >= 9 and m.get("moment_type") in FREEZE_TYPES and key <= d - 1.0:
        freeze = {"at": round(key, 2), "duration": round(min(0.15 + 0.02 * (intensity - 9), 0.25), 2)}
        plan["reasons"].append(f"freeze {freeze['duration']}s on the payoff ({m.get('moment_type')}, intensity {intensity})")
    amount = round(min(0.06 + 0.012 * (intensity - 6), 0.14), 3)
    hold = key + 0.5 + (freeze["duration"] if freeze else 0.0)
    plan["zoom"] = {"start": round(max(key - 0.55, 0.0), 2), "peak": round(key - 0.15, 2),
                    "hold_until": round(hold, 2), "end": round(hold + 0.45, 2), "amount": amount}
    plan["freeze"] = freeze
    plan["reasons"].append(f"punch-in {int(amount * 100)}% into the payoff at {key:.1f}s")
    return plan


def _overlap(a0, a1, segments):
    total = 0.0
    for s in segments or []:
        total += max(0.0, min(a1, s["end"]) - max(a0, s["start"]))
    return total


def _best_start(earliest, latest, dur, speech):
    """Start in [earliest, latest] (25 ms grid of 0.25s) minimising overlap with
    the streamer's speech; ties go to the earliest start. None if the line
    can't be placed without talking over >50% of itself."""
    if latest < earliest:
        return None
    best, best_ov = None, None
    t = earliest
    while t <= latest + 1e-6:
        ov = _overlap(t, t + dur, speech)
        if best is None or ov < best_ov - 1e-9:
            best, best_ov = t, ov
        t = round(t + 0.25, 3)
    if best_ov is not None and best_ov > 0.5 * dur:
        return None
    return round(best, 2)


def place_narration(lines, clip_duration, key=None, freeze_duration=0.0, speech=None):
    """Place voiced lines on the main-clip timeline.

    lines:  [{'kind': 'hook'|'setup'|'tag', 'text', 'duration'}] in speaking order
    key:    trustworthy payoff time, or None
    speech: [{'start','end'}] streamer-speech segments (to avoid talking over)
    -> (placed, end_hold): placed lines gain 'start'/'end'; end_hold is how many
       seconds the last frame must be held so a closing tag can finish (<= 1.5s).
    Lines that don't fit are dropped, never squeezed.
    """
    d = float(clip_duration)
    p0 = (key - PAYOFF_PRE) if key is not None else None
    p1 = (key + freeze_duration + PAYOFF_POST) if key is not None else None
    placed, end_hold, cursor = [], 0.0, None

    for line in lines:
        dur, kind = float(line["duration"]), line["kind"]
        if kind == "hook":
            earliest = HOOK_START
            latest = (p0 - dur - 0.05) if p0 is not None else d * 0.35
        elif kind == "setup":
            earliest = (cursor + LINE_GAP) if cursor is not None else HOOK_START
            latest = (p0 - dur - 0.15) if p0 is not None else d * 0.55 - dur
        else:  # tag — lands AFTER the payoff
            base = (cursor + LINE_GAP) if cursor is not None else HOOK_START
            earliest = max(base, p1) if p1 is not None else max(base, d * 0.7)
            latest = d - 0.1 + END_HOLD_MAX - dur
        start = _best_start(earliest, latest, dur, speech)
        if start is None:
            print(f"Narration '{kind}' line doesn't fit the timeline — dropped")
            continue
        end = round(start + dur, 2)
        if kind == "tag":
            end_hold = max(0.0, end - (d - 0.1))
            if end_hold > END_HOLD_MAX:
                print("Narration 'tag' line would need too long an end hold — dropped")
                continue
        placed.append({**line, "start": start, "end": end})
        cursor = end
    return placed, round(end_hold, 2)
