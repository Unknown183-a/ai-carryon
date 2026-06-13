# agents/video_agent.py
from moviepy import *
import numpy as np
import os
import glob
import shutil
import datetime


def parse_srt(srt_path):
    with open(srt_path, "r") as f:
        content = f.read()

    blocks = content.strip().split("\n\n")
    captions = []

    for block in blocks:
        lines = block.split("\n")
        if len(lines) < 3:
            continue
        time_line = lines[1]
        text = " ".join(lines[2:])
        start_str, end_str = time_line.split(" --> ")

        def to_seconds(t):
            h, m, s_ms = t.split(":")
            s, ms = s_ms.split(",")
            return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000

        captions.append((to_seconds(start_str), to_seconds(end_str), text))

    return captions


def get_background_images():
    folder = "assets/backgrounds"
    images = []

    if os.path.isdir(folder):
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            images.extend(glob.glob(os.path.join(folder, ext)))

    images.sort()

    if not images:
        fallback = "assets/background.jpg"
        if os.path.exists(fallback):
            images = [fallback]

    return images


def create_video():
    audio_path = "output/voice.mp3"
    srt_path = "output/captions.srt"
    music_path = "assets/music/bg_music.mp3"
    font_path = "assets/fonts/Arial-Bold.ttf"

    # --- Audio ---
    voice = AudioFileClip(audio_path)
    duration = voice.duration

    # --- Background images with fast cuts (2-3s per image) ---
    images = get_background_images()
    if not images:
        raise FileNotFoundError("No background images found.")

    # Repeat images if needed to fill duration
    cut_duration = 3.0  # seconds per image
    needed = int(duration / cut_duration) + 1
    images_looped = (images * (needed // len(images) + 1))[:needed]

    clips = []
    for img_path in images_looped:
        clip = ImageClip(img_path).with_duration(cut_duration)
        clip = clip.resized((1080, 1920))

        # Dark overlay for readability
        overlay = ColorClip(
            size=(1080, 1920),
            color=[0, 0, 0]
        ).with_duration(cut_duration).with_opacity(0.5)

        clips.append(CompositeVideoClip([clip, overlay]))

    bg = concatenate_videoclips(clips, method="compose").subclipped(0, duration)

    # --- Word-by-word captions ---
    captions = parse_srt(srt_path)
    text_clips = []

    for start, end, text in captions:
        txt = (
            TextClip(
                text=text.upper(),
                font_size=90,
                color="white",
                stroke_color="black",
                stroke_width=3,
                size=(900, None),
                method="caption",
                font=font_path
            )
            .with_position(("center", 0.65), relative=True)
            .with_start(start)
            .with_end(end)
        )
        text_clips.append(txt)

    # --- Background music ---
    audio_clips = [voice]
    if os.path.exists(music_path):
        music = AudioFileClip(music_path).subclipped(0, duration)
        music = music.with_effects([afx.MultiplyVolume(0.15)])
        combined_audio = CompositeAudioClip([voice, music])
        final_audio = combined_audio
    else:
        final_audio = voice

    # --- Compose final ---
    final = CompositeVideoClip([bg, *text_clips]).with_audio(final_audio)

    os.makedirs("output", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"output/video_{timestamp}.mp4"

    final.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast"
    )

    latest_path = "output/final_video.mp4"
    shutil.copy(output_path, latest_path)

    return latest_path
