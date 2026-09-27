"""
agents_bhakti/silent_video_agent.py

Voice-free devotional Shorts: stitches Pexels devotional B-roll into a
fixed-duration silent video and sets a CC-licensed instrumental track as
the ONLY audio (no narration, no captions, no on-screen text).

Kept fully separate from agents/video_agent.py so the shared
English/Hindi narrated-video pipeline is completely untouched.
"""

import os
import shutil
import subprocess
import datetime

from agents.video_agent import get_ffmpeg, SHORTS_WIDTH, SHORTS_HEIGHT, get_pexels_clips

DEFAULT_DURATION = 35.0  # seconds — sweet spot for a devotional mood Short


def _loop_trim_fade_music(ffmpeg, music_path, duration, out_path):
    cmd = [
        ffmpeg, "-y",
        "-stream_loop", "-1",
        "-i", music_path,
        "-t", str(duration),
        "-af", (
            f"afade=t=in:st=0:d=1.5,"
            f"afade=t=out:st={max(duration - 2, 0)}:d=2,"
            f"volume=0.9"
        ),
        "-c:a", "aac",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Music loop/trim failed: {result.stderr[-400:]}")


def create_silent_music_video(music_path, duration=None):
    if not music_path or not os.path.exists(music_path):
        raise RuntimeError(
            "create_silent_music_video requires a valid music_path — none was provided"
        )

    clip_paths = get_pexels_clips()
    if not clip_paths:
        raise RuntimeError("No Pexels clips found in assets/pexels_clips — cannot render.")

    ffmpeg = get_ffmpeg()
    os.makedirs("output", exist_ok=True)
    duration = duration or DEFAULT_DURATION
    n = len(clip_paths)
    per_clip = duration / n
    print(
        f"[silent_video] Target duration: {duration:.1f}s across {n} Pexels clips "
        f"(~{per_clip:.1f}s each), music-only audio"
    )

    segment_paths = []
    for i, clip_path in enumerate(clip_paths):
        seg_path = f"output/pexels_seg_{i}.mp4"
        cmd = [
            ffmpeg, "-y",
            "-stream_loop", "-1",
            "-i", clip_path,
            "-t", str(per_clip),
            "-vf", f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=increase,"
                   f"crop={SHORTS_WIDTH}:{SHORTS_HEIGHT},setsar=1,fps=30",
            "-an",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-pix_fmt", "yuv420p",
            seg_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[silent_video] Segment {i} trim failed, skipping: {result.stderr[-300:]}")
            continue
        segment_paths.append(seg_path)

    if not segment_paths:
        raise RuntimeError("All Pexels clip segments failed to render.")

    concat_path = "output/pexels_concat.txt"
    with open(concat_path, "w") as f:
        for sp in segment_paths:
            f.write("file '" + os.path.abspath(sp) + "'\n")

    silent_bg = "output/pexels_bg_silent.mp4"
    concat_cmd = [
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_path,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p",
        silent_bg,
    ]
    result = subprocess.run(concat_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Pexels concat failed: {result.stderr[-500:]}")

    music_ready = "output/music_ready.aac"
    _loop_trim_fade_music(ffmpeg, music_path, duration, music_ready)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"output/video_{timestamp}.mp4"
    cmd = [
        ffmpeg, "-y",
        "-i", silent_bg,
        "-i", music_ready,
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac",
        "-shortest",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Final mux failed: {result.stderr[-500:]}")

    latest = "output/final_video.mp4"
    shutil.copy(output_path, latest)
    print(f"[silent_video] Music-only devotional video ready: {output_path}")
    return latest
