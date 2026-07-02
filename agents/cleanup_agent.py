"""
agents/cleanup_agent.py — Post-upload disk cleanup

Deletes per-video temp files after a successful upload, and runs a
safety sweep on startup to remove any leftover files from crashed
runs (older than a threshold) so disk usage never grows unbounded.
"""

import os
import glob
import time


PER_VIDEO_FILES = [
    "output/voice.mp3",
    "output/voice.wav",
    "output/captions.srt",
    "output/captions_words.json",
    "output/thumbnail.jpg",
    "output/final_video.mp4",
    "output/bg_0.jpg",
    "output/bg_1.jpg",
    "output/bg_2.jpg",
    "output/bg_3.jpg",
]


def cleanup_after_upload(video_path: str, log_fn=print):
    """Delete the just-uploaded video file and its associated temp assets."""
    deleted = []
    failed = []

    # Delete the main video file
    if video_path and os.path.exists(video_path):
        try:
            os.remove(video_path)
            deleted.append(video_path)
        except Exception as e:
            failed.append((video_path, str(e)))

    # Delete known per-video temp files
    for f in PER_VIDEO_FILES:
        if os.path.exists(f):
            try:
                os.remove(f)
                deleted.append(f)
            except Exception as e:
                failed.append((f, str(e)))

    # Clean up flow_clips folder (Google Flow/Veo clips, if used)
    for clip in glob.glob("assets/flow_clips/*.mp4"):
        try:
            os.remove(clip)
            deleted.append(clip)
        except Exception as e:
            failed.append((clip, str(e)))

    log_fn(f"🧹 Cleanup: removed {len(deleted)} file(s)" + (f", {len(failed)} failed" if failed else ""))
    if failed:
        for f, err in failed:
            log_fn(f"   Could not delete {f}: {err}")

    return deleted, failed


def sweep_old_videos(max_age_hours: int = 24, log_fn=print):
    """
    Safety sweep — delete any output/video_*.mp4 files older than
    max_age_hours. Catches leftovers from crashed runs where the
    normal post-upload cleanup never ran.
    """
    cutoff = time.time() - (max_age_hours * 3600)
    pattern = "output/video_*.mp4"
    deleted = []

    for path in glob.glob(pattern):
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                deleted.append(path)
        except Exception as e:
            log_fn(f"Sweep: could not delete {path}: {e}")

    if deleted:
        log_fn(f"🧹 Startup sweep: removed {len(deleted)} old video file(s) (>{max_age_hours}h old)")
    else:
        log_fn(f"🧹 Startup sweep: no old video files to remove")

    return deleted
