# agents_cricket/video_agent.py
"""
Lightweight video renderer for Render's free tier (512MB RAM, 0.15 CPU).
Trades some visual polish for reliability: lower resolution, simple
crossfade zoom instead of per-frame Ken Burns math, no held frame buffers.
"""
import os
from moviepy import (
    ImageClip, AudioFileClip, CompositeVideoClip, TextClip,
    concatenate_videoclips, vfx
)

# Portrait Shorts, but smaller than your English/Hindi 1080x1920 —
# this alone cuts render memory roughly 4x
WIDTH, HEIGHT = 540, 960
FPS = 20


def _make_clip(image_path, duration):
    clip = ImageClip(image_path).resized(height=HEIGHT)
    if clip.w < WIDTH:
        clip = clip.resized(width=WIDTH)
    clip = clip.cropped(
        x_center=clip.w / 2, y_center=clip.h / 2, width=WIDTH, height=HEIGHT
    )
    # simple, cheap zoom — no per-frame PIL math, moviepy handles it lazily
    clip = clip.with_effects([vfx.Resize(lambda t: 1 + 0.04 * (t / duration))])
    clip = clip.with_duration(duration)
    return clip


def create_video(audio_path="output/voice.mp3", images_folder="assets/backgrounds",
                  output_path="output/final_video.mp4"):
    os.makedirs("output", exist_ok=True)

    audio = AudioFileClip(audio_path)
    total_duration = audio.duration

    images = sorted([
        os.path.join(images_folder, f) for f in os.listdir(images_folder)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ])
    if not images:
        raise RuntimeError("No background images found for video render")

    per_image = total_duration / len(images)
    clips = [_make_clip(img, per_image) for img in images]

    video = concatenate_videoclips(clips, method="compose")
    video = video.with_audio(audio)

    video.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",   # trades file size for speed/memory — right call on 0.15 CPU
        threads=1,
        logger=None,
    )

    audio.close()
    video.close()
    return output_path
