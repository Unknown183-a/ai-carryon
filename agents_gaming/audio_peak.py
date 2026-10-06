# agents_gaming/audio_peak.py
"""
Audio helpers for Gaming V2 Sprint 2 (no API calls, no extra dependencies).

The moment analyzer only sees 5 frames, so its `key_timestamp` (the payoff) can
be off by a second or more. In a gaming highlight the payoff is almost always
also the LOUDEST moment (scream, explosion, chat-reaction, kill sound), and we
have the clip's real audio — so we snap the estimate to the loudest burst
near it. A zoom or freeze-frame that lands on the actual peak looks edited; one
that lands a second early looks like a bug.
"""
import array
import math
import os
import shutil
import subprocess

SAMPLE_RATE = 8000   # plenty for loudness; keeps decoding instant


def ffmpeg_bin():
    """System ffmpeg first (known to ship libass/filters on the runner), then imageio's."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def has_audio_stream(path):
    r = subprocess.run([ffmpeg_bin(), "-i", path], capture_output=True, text=True)
    return " Audio:" in (r.stderr or "")


def loudness_profile(path, step=0.1):
    """RMS loudness per `step`-second window, as a list. [] if there is no
    decodable audio."""
    try:
        r = subprocess.run(
            [ffmpeg_bin(), "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
             "-f", "s16le", "-"],
            capture_output=True, timeout=60,
        )
    except Exception:
        return []
    if r.returncode != 0 or not r.stdout:
        return []
    samples = array.array("h")
    samples.frombytes(r.stdout[: len(r.stdout) // 2 * 2])
    win = max(int(SAMPLE_RATE * step), 1)
    out = []
    for i in range(0, len(samples) - win + 1, win):
        chunk = samples[i:i + win]
        out.append(math.sqrt(sum(s * s for s in chunk) / win))
    return out


def refine_key_timestamp(path, key, radius=1.5, step=0.1, min_ratio=1.8):
    """Snap `key` to the loudest burst within +/- `radius` seconds.

    Only moves when the burst clearly stands out (>= `min_ratio` x the clip's
    median loudness); otherwise returns `key` unchanged. Returns
    (new_key, changed: bool). Never raises.
    """
    try:
        prof = loudness_profile(path, step)
        if len(prof) < 10 or key is None:
            return key, False
        ordered = sorted(prof)
        median = max(ordered[len(ordered) // 2], 1.0)
        lo = max(int((key - radius) / step), 0)
        hi = min(int((key + radius) / step) + 1, len(prof))
        if hi <= lo:
            return key, False
        # smooth over 3 windows so one clipped sample can't win
        def smooth(i):
            seg = prof[max(i - 1, 0):i + 2]
            return sum(seg) / len(seg)
        best = max(range(lo, hi), key=smooth)
        if smooth(best) < median * min_ratio:
            return key, False
        new_key = round((best + 0.5) * step, 2)
        return new_key, abs(new_key - key) >= step
    except Exception as e:
        print(f"Audio peak refinement skipped: {e}")
        return key, False
