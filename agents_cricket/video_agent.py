# agents_cricket/video_agent.py
"""Cricket video renderer. Prefers dynamic Pexels stock *video* clips (same
approach English/Hindi already use) with burned-in aesthetic word-highlight
captions; falls back to the original static-image renderer — now also
caption-burned via burn_captions() — if too few clips were fetched this run.
"""
import os
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

from agents.video_agent import _create_video_from_pexels_clips, burn_captions, get_pexels_clips

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


def _create_static_video(audio_path, images_folder, output_path):
    """Original low-memory static-image renderer, kept as the fallback path
    for when too few Pexels video clips came back this run."""
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


def create_video(audio_path="output/voice.mp3", images_folder="assets/backgrounds",
                  output_path="output/final_video.mp4", use_pexels_clips=False):
    os.makedirs("output", exist_ok=True)

    pexels_clips = get_pexels_clips() if use_pexels_clips else []
    if pexels_clips:
        print(f"Using {len(pexels_clips)} Pexels clips as cricket background")
        return _create_video_from_pexels_clips(pexels_clips, audio_path, "output/captions.srt")

    raw_path = _create_static_video(audio_path, images_folder, output_path)
    return burn_captions(raw_path, output_path)
