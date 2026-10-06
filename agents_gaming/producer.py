# agents_gaming/producer.py
"""
Gaming V2 Sprint 2 — script -> finished Short.

    approved script ──> narration lines ──> per-line TTS (voice style from the moment)
         clip + moment ──> edit plan (zoom / freeze, only when the payoff time is trusted)
         lines + plan ──> timeline (never over the payoff, never over the streamer)
         everything ──> ffmpeg render (game audio kept + ducked, captions in safe zones)

Kept out of scheduler_gaming.py so it can be tested without the scheduler's DB,
Twitch or upload dependencies.
"""
import os
import re

from agents_gaming.editor_agent import place_narration, plan_edit
from agents_gaming.moment_analyzer import probe_duration
from agents_gaming.video_renderer import render_gaming_video
from agents_gaming.voice_agent import synth_lines, voice_style_for


def script_to_lines(script):
    """Split an approved script into voiced lines: first = hook, last = tag (when
    there are 3+), the middle = setup. Pause markers and blank lines are ignored."""
    raw = [re.sub(r"\.{2,}|\u2026", " ", ln).strip() for ln in str(script or "").splitlines()]
    raw = [" ".join(ln.split()) for ln in raw if ln and re.search(r"\w", ln)]
    if not raw:
        return []
    if len(raw) == 1:
        return [{"kind": "hook", "text": raw[0]}]
    if len(raw) == 2:
        return [{"kind": "hook", "text": raw[0]}, {"kind": "setup", "text": raw[1]}]
    return [{"kind": "hook", "text": raw[0]},
            {"kind": "setup", "text": " ".join(raw[1:-1])},
            {"kind": "tag", "text": raw[-1]}]


def produce_video(clip_path, script, hook, moment, transcript=None, cold_open=None,
                  out_path="output/final_video.mp4", work_dir="output/gaming_render"):
    """Returns the rendered video path. Raises on render failure (the scheduler
    treats that as 'do not upload', not as a reason to publish something degraded)."""
    os.makedirs(work_dir, exist_ok=True)
    lines = script_to_lines(script)
    hook_text = (hook or {}).get("text") or (lines[0]["text"] if lines else "")

    duration = probe_duration(clip_path)
    if not duration:
        raise RuntimeError("cannot read clip duration")
    plan = plan_edit(moment, duration)
    for reason in plan["reasons"]:
        print(f"Edit plan: {reason}")

    style = voice_style_for(moment)
    voiced = synth_lines(lines, style, work_dir)
    speech = (transcript or {}).get("segments")
    placed, end_hold = place_narration(
        voiced, duration, key=plan["key"],
        freeze_duration=(plan["freeze"] or {}).get("duration", 0.0), speech=speech,
    )
    print(f"Narration: voice style '{style}', {len(placed)}/{len(lines)} lines placed "
          f"{[(p['kind'], p['start'], p['end']) for p in placed]}")

    result = render_gaming_video(
        clip_path, placed, plan, hook_text, moment, cold_open=cold_open,
        end_hold=end_hold, out_path=out_path, work_dir=work_dir,
    )
    return result["path"]
