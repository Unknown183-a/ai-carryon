"""
agents_bhakti/narrated_video_agent.py

Narrated devotional Shorts: Hindi voiceover (Sarvam) over Pexels devotional
B-roll, with the bhajan/chant track (from music_agent) playing underneath.

Difference from the shared Pexels renderer in agents/video_agent.py:
  * the bhajan is *ducked* (sidechain-compressed) whenever the narrator speaks,
    so a vocal chant/kirtan track never fights the Hindi narration
  * the music starts 1.5s before the voice fades in and rings out ~2s after
    the narration ends, so the Short opens and closes on the bhajan
  * shared English/Hindi rendering is left completely untouched
"""

import os
import shutil
import subprocess
import datetime

from agents.video_agent import SHORTS_WIDTH, SHORTS_HEIGHT, get_pexels_clips

LEAD_IN = 1.5      # seconds of bhajan before the voice starts
TAIL = 2.0         # seconds of bhajan after the voice ends
MUSIC_VOLUME = 0.55  # pre-duck level; ducking pulls it well below the voice


def _ffmpeg():
    try:
        from agents.video_agent import get_ffmpeg
        return get_ffmpeg()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


def _duration(path):
    try:
        from agents.video_agent import get_audio_duration
        return get_audio_duration(path)
    except Exception:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True,
        )
        return float(out.stdout.strip())


def _build_background(ffmpeg, clip_paths, total, hook=None):
    n = len(clip_paths)
    # Hook Engine: the hook opens the video (it covers the bhajan lead-in and the
    # first words) and replaces the first seconds of B-roll; total is unchanged.
    from agents.hook_render import prepare_hook_segment
    hook_seg, _hook_dur, per_clip = prepare_hook_segment(
        ffmpeg, hook, total, n, SHORTS_WIDTH, SHORTS_HEIGHT, out_path="output/bhakti_hook_seg.mp4")
    segs = [hook_seg] if hook_seg else []
    for i, clip in enumerate(clip_paths):
        seg = f"output/bhakti_seg_{i}.mp4"
        r = subprocess.run([
            ffmpeg, "-y", "-stream_loop", "-1", "-i", clip, "-t", str(per_clip),
            "-vf", f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=increase,"
                   f"crop={SHORTS_WIDTH}:{SHORTS_HEIGHT},setsar=1,fps=30",
            "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-pix_fmt", "yuv420p", seg,
        ], capture_output=True, text=True)
        if r.returncode == 0:
            segs.append(seg)
        else:
            print(f"[narrated_video] segment {i} failed, skipping: {r.stderr[-300:]}")
    if not segs:
        raise RuntimeError("All Pexels clip segments failed to render.")

    concat_txt = "output/bhakti_concat.txt"
    with open(concat_txt, "w") as f:
        for s in segs:
            f.write("file '" + os.path.abspath(s) + "'\n")

    bg = "output/bhakti_bg_silent.mp4"
    r = subprocess.run([
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", concat_txt,
        "-t", str(total), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p", bg,
    ], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Background concat failed: {r.stderr[-500:]}")
    return bg


def create_narrated_music_video(music_path, audio_path="output/voice.mp3",
                                ass_path="output/captions.ass",
                                music_volume=MUSIC_VOLUME, hook=None):
    """Render voiceover + ducked bhajan over Pexels clips. Returns the path
    to output/final_video.mp4."""
    if not music_path or not os.path.exists(music_path):
        raise RuntimeError("create_narrated_music_video needs a valid music_path")
    if not os.path.exists(audio_path):
        raise RuntimeError(f"Voiceover not found at {audio_path}")

    clips = get_pexels_clips()
    if not clips:
        raise RuntimeError("No Pexels clips in assets/pexels_clips — cannot render.")

    ffmpeg = _ffmpeg()
    os.makedirs("output", exist_ok=True)

    voice_len = _duration(audio_path)
    total = LEAD_IN + voice_len + TAIL
    print(f"[narrated_video] voice {voice_len:.1f}s -> total {total:.1f}s, {len(clips)} clips")

    bg = _build_background(ffmpeg, clips, total, hook=hook)

    lead_ms = int(LEAD_IN * 1000)
    fade_out_start = max(total - TAIL - 0.5, 0)
    audio_graph = (
        f"[1:a]adelay={lead_ms}|{lead_ms},apad=whole_dur={total:.2f},asplit=2[vkey][vmix];"
        f"[2:a]volume={music_volume},afade=t=in:st=0:d=1.5,"
        f"afade=t=out:st={fade_out_start:.2f}:d={TAIL + 0.5:.2f}[bg];"
        f"[bg][vkey]sidechaincompress=threshold=0.03:ratio=8:attack=30:release=700:makeup=1[duck];"
        f"[duck][vmix]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[aout]"
    )

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = f"output/video_{timestamp}.mp4"
    has_caps = os.path.exists(ass_path)

    def run(with_caps):
        cmd = [ffmpeg, "-y", "-i", bg, "-i", audio_path,
               "-stream_loop", "-1", "-i", music_path,
               "-filter_complex", audio_graph]
        if with_caps:
            cmd += ["-vf", f"ass={ass_path}"]
        cmd += ["-map", "0:v", "-map", "[aout]", "-t", f"{total:.2f}",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", out]
        return subprocess.run(cmd, capture_output=True, text=True)

    r = run(has_caps)
    if r.returncode != 0 and has_caps:
        print(f"[narrated_video] caption burn failed, retrying without: {r.stderr[-300:]}")
        r = run(False)
    if r.returncode != 0:
        raise RuntimeError(f"Narrated render failed: {r.stderr[-600:]}")

    latest = "output/final_video.mp4"
    shutil.copy(out, latest)
    print(f"[narrated_video] ready: {out}")
    return latest
