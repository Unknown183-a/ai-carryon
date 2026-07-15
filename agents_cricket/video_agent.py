# agents_cricket/video_agent.py
"""Lightweight, low-memory video renderer for Render's free tier.
No Ken Burns zoom for now — static crop-to-fit clips, correctness first."""
import os
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

WIDTH, HEIGHT = 540, 960
FPS = 20


def _make_clip(image_path, duration):
    clip = ImageClip(image_path).resized(height=HEIGHT)
    if clip.w < WIDTH:
        clip = clip.resized(width=WIDTH)
    clip = clip.cropped(
        x_center=clip.w / 2, y_center=clip.h / 2, width=WIDTH, height=HEIGHT
    )
    return clip.with_duration(duration)


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
        preset="ultrafast",
        threads=1,
        logger=None,
    )

    audio.close()
    video.close()
    return output_path
