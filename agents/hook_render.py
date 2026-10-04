# agents/hook_render.py
"""
Hook rendering helper shared by every renderer
(agents/video_agent.py, agents_bhakti/narrated_video_agent.py,
agents_bhakti/silent_video_agent.py; agents_cricket/video_agent.py and the
gaming channel go through the shared one).

Design rule: the hook REPLACES the first `hook_duration` seconds of the
background — it never lengthens the video. The voiceover, SRT/ASS captions and
music are all timed against the original total, so nothing can drift.

    total = 30s, 4 clips, no hook : 4 x 7.5s
    total = 30s, 4 clips, 2s hook : 2s hook + 4 x 7.0s

Dependency-free on purpose (no LLM / network imports) so renderers can import
it safely.
"""
import os
import subprocess

MAX_HOOK_FRACTION = 0.25   # a hook never takes more than a quarter of the video


def hook_is_usable(hook):
    """True if `hook` is a dict pointing at a real file with a positive duration."""
    if not isinstance(hook, dict):
        return False
    path = hook.get("path")
    try:
        return bool(path) and os.path.exists(path) and float(hook.get("duration", 0)) > 0
    except (TypeError, ValueError):
        return False


def render_hook_segment(ffmpeg, hook, out_path, width, height):
    """Render the hook to an exact-length, silent, Shorts-sized segment.
    Encoding params match the renderers' other segments so the concat demuxer
    can join them. Returns out_path, or None on failure (never raises)."""
    dur = float(hook["duration"])
    start = max(float(hook.get("start", 0) or 0), 0.0)
    cmd = [
        ffmpeg, "-y",
        "-ss", f"{start:.3f}",
        "-stream_loop", "-1",          # same safety net as the other segments:
        "-i", hook["path"],            # never come out shorter than requested
        "-t", f"{dur:.3f}",
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,"
               f"crop={width}:{height},setsar=1,fps=30",
        "-an",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p",
        out_path,
    ]
    try:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        r = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as e:
        print(f"[hook] segment render error: {e}")
        return None
    if r.returncode != 0 or not os.path.exists(out_path):
        print(f"[hook] segment render failed: {(r.stderr or '')[-300:]}")
        return None
    return out_path


def prepare_hook_segment(ffmpeg, hook, total, n_clips, width, height,
                         out_path="output/hook_seg.mp4"):
    """Returns (hook_segment_path_or_None, hook_seconds, per_clip_seconds).

    With no usable hook (or a failed render) this returns
    (None, 0.0, total / n_clips) — exactly the renderers' original behaviour."""
    n = max(int(n_clips), 1)
    if not hook_is_usable(hook):
        return None, 0.0, total / n
    dur = min(float(hook["duration"]), total * MAX_HOOK_FRACTION)
    if dur <= 0.3:
        return None, 0.0, total / n
    seg = render_hook_segment(ffmpeg, dict(hook, duration=dur), out_path, width, height)
    if not seg:
        return None, 0.0, total / n
    print(f"[hook] {hook.get('provider', '?')} hook {dur:.1f}s opens the video "
          f"({hook.get('selection_reason', 'selected')})")
    return seg, dur, (total - dur) / n
