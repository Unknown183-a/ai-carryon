# agents/video_agent.py
from moviepy import *
import numpy as np
import os
import glob
import shutil
import datetime

SHORTS_WIDTH = 1080
SHORTS_HEIGHT = 1920
SHORTS_MAX_DURATION = 60

FONT_PATH = "assets/fonts/Arial-Bold.ttf"
FONT_SIZE = 90
HIGHLIGHT_COLOR = "yellow"
SHADOW_COLOR = "black"


def zoom_in_effect(clip, zoom_ratio=0.03):
    def effect(get_frame, t):
        img = get_frame(t)
        h, w = img.shape[:2]
        zoom = 1 + (zoom_ratio * t)
        new_w, new_h = int(w * zoom), int(h * zoom)
        from PIL import Image
        pil_img = Image.fromarray(img)
        pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - w) // 2
        top = (new_h - h) // 2
        pil_img = pil_img.crop((left, top, left + w, top + h))
        return np.array(pil_img)
    return clip.transform(effect)


def resize_to_shorts(image_path):
    from PIL import Image
    img = Image.open(image_path).convert("RGB")
    target_w, target_h = SHORTS_WIDTH, SHORTS_HEIGHT
    target_ratio = target_w / target_h
    orig_w, orig_h = img.size
    orig_ratio = orig_w / orig_h
    if orig_ratio > target_ratio:
        new_w = int(orig_h * target_ratio)
        left = (orig_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, orig_h))
    else:
        new_h = int(orig_w / target_ratio)
        top = (orig_h - new_h) // 2
        img = img.crop((0, top, orig_w, top + new_h))
    img = img.resize((target_w, target_h), Image.LANCZOS)
    temp_path = image_path.replace(".jpg", "_shorts.jpg").replace(".png", "_shorts.jpg")
    img.save(temp_path, "JPEG", quality=95)
    return temp_path


def get_background_images():
    folder = "assets/backgrounds"
    images = []
    if os.path.isdir(folder):
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            images.extend(glob.glob(os.path.join(folder, ext)))
    images = [i for i in images if "_shorts" not in i]
    images.sort()
    if not images:
        fallback = "assets/background.jpg"
        if os.path.exists(fallback):
            images = [fallback]
    return images


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


def make_word_caption_clip(word, start, end):
    duration = end - start
    txt = (
        TextClip(
            text=word.upper(),
            font_size=FONT_SIZE,
            color=HIGHLIGHT_COLOR,
            stroke_color=SHADOW_COLOR,
            stroke_width=5,
            font=FONT_PATH,
            method="label"
        )
        .with_position(("center", 0.6), relative=True)
        .with_start(start)
        .with_duration(duration)
    )
    return txt


def create_video():
    audio_path = "output/voice.mp3"
    srt_path = "output/captions.srt"

    audio = AudioFileClip(audio_path)
    duration = audio.duration

    if duration > SHORTS_MAX_DURATION:
        print(f"WARNING: Audio is {duration:.1f}s — over 60s Shorts limit!")
    else:
        print(f"Duration: {duration:.1f}s — Shorts ready!")

    images = get_background_images()
    if not images:
        raise FileNotFoundError("No background images found.")

    n = len(images)
    per_image = duration / n

    clips = []
    for img_path in images:
        shorts_path = resize_to_shorts(img_path)
        clip = ImageClip(shorts_path).with_duration(per_image)
        clip = zoom_in_effect(clip)
        clips.append(clip)

    bg = concatenate_videoclips(clips, method="compose")

    # Force correct shorts dimensions
    bg = bg.resized((SHORTS_WIDTH, SHORTS_HEIGHT))

    # Word-by-word captions
    word_timings = parse_srt(srt_path)
    text_clips = []

    for start, end, word in word_timings:
        txt_clip = make_word_caption_clip(word, start, end)
        text_clips.append(txt_clip)

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
