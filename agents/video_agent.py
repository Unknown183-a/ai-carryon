# agents/video_agent.py
from moviepy import *
import numpy as np
import os
import glob
import shutil
import datetime

# YouTube Shorts dimensions
SHORTS_WIDTH = 1080
SHORTS_HEIGHT = 1920
SHORTS_MAX_DURATION = 60  # seconds


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


def zoom_in_effect(clip, zoom_ratio=0.04):
    """Slow Ken Burns zoom effect"""
    def effect(get_frame, t):
        img = get_frame(t)
        h, w = img.shape[:2]
        zoom = 1 + (zoom_ratio * t)
        new_w, new_h = int(w * zoom), int(h * zoom)

        from PIL import Image
        pil_img = Image.fromarray(img)
        pil_img = pil_img.resize((new_w, new_h))

        left = (new_w - w) // 2
        top = (new_h - h) // 2
        pil_img = pil_img.crop((left, top, left + w, top + h))

        return np.array(pil_img)

    return clip.transform(effect)


def resize_to_shorts(image_path):
    """Resize and center-crop image to 1080x1920 (9:16)"""
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    target_w, target_h = SHORTS_WIDTH, SHORTS_HEIGHT
    target_ratio = target_w / target_h

    orig_w, orig_h = img.size
    orig_ratio = orig_w / orig_h

    if orig_ratio > target_ratio:
        # Too wide — crop sides
        new_w = int(orig_h * target_ratio)
        left = (orig_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, orig_h))
    else:
        # Too tall — crop top/bottom
        new_h = int(orig_w / target_ratio)
        top = (orig_h - new_h) // 2
        img = img.crop((0, top, orig_w, top + new_h))

    img = img.resize((target_w, target_h), Image.LANCZOS)

    # Save resized version to temp path
    temp_path = image_path.replace(".jpg", "_shorts.jpg").replace(".png", "_shorts.jpg")
    img.save(temp_path, "JPEG", quality=95)
    return temp_path


def get_background_images():
    folder = "assets/backgrounds"
    images = []

    if os.path.isdir(folder):
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            images.extend(glob.glob(os.path.join(folder, ext)))

    # Exclude already-resized shorts versions
    images = [i for i in images if "_shorts" not in i]
    images.sort()

    if not images:
        fallback = "assets/background.jpg"
        if os.path.exists(fallback):
            images = [fallback]

    return images


def create_video():
    audio_path = "output/voice.mp3"
    srt_path = "output/captions.srt"

    audio = AudioFileClip(audio_path)
    duration = audio.duration

    # Warn if too long for Shorts
    if duration > SHORTS_MAX_DURATION:
        print(f"⚠️  WARNING: Audio is {duration:.1f}s — YouTube Shorts must be under 60s!")
    else:
        print(f"✅ Duration: {duration:.1f}s — within Shorts limit")

    images = get_background_images()

    if not images:
        raise FileNotFoundError("No background images found.")

    n = len(images)
    per_image = duration / n

    clips = []
    for img_path in images:
        # Resize each image to exact Shorts dimensions
        shorts_path = resize_to_shorts(img_path)

        clip = ImageClip(shorts_path).with_duration(per_image)
        clip = zoom_in_effect(clip, zoom_ratio=0.03)
        clips.append(clip)

    bg = concatenate_videoclips(clips, method="compose")

    captions = parse_srt(srt_path)
    text_clips = []

    for start, end, text in captions:
        txt = (
            TextClip(
                text=text.upper(),
                font_size=80,  # slightly larger for 1080p
                color="white",
                stroke_color="black",
                stroke_width=4,
                size=(SHORTS_WIDTH - 120, None),
                method="caption",
                font="/System/Library/Fonts/Supplemental/Arial Bold.ttf"
            )
            .with_position(("center", "center"))
            .with_start(start)
            .with_end(end)
        )
        text_clips.append(txt)

    final = CompositeVideoClip(
        [bg, *text_clips],
        size=(SHORTS_WIDTH, SHORTS_HEIGHT)
    ).with_audio(audio)

    os.makedirs("output", exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"output/video_{timestamp}.mp4"

    final.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="medium"
    )

    latest_path = "output/final_video.mp4"
    shutil.copy(output_path, latest_path)

    return latest_path