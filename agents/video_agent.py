import os
import glob
import shutil
import datetime
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

def get_ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

SHORTS_WIDTH = 1080
SHORTS_HEIGHT = 1920
import platform
if platform.system() == "Darwin":
    FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
else:
    FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

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

def get_audio_duration(audio_path):
    from moviepy import AudioFileClip
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    audio.close()
    return duration

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

def resize_image(image_path, output_path):
    img = Image.open(image_path).convert("RGB")
    orig_w, orig_h = img.size
    target_ratio = SHORTS_WIDTH / SHORTS_HEIGHT
    orig_ratio = orig_w / orig_h
    if orig_ratio > target_ratio:
        new_w = int(orig_h * target_ratio)
        left = (orig_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, orig_h))
    else:
        new_h = int(orig_w / target_ratio)
        top = (orig_h - new_h) // 2
        img = img.crop((0, top, orig_w, top + new_h))
    # Make larger for Ken Burns zoom
    img = img.resize((int(SHORTS_WIDTH * 1.3), int(SHORTS_HEIGHT * 1.3)), Image.LANCZOS)
    img.save(output_path, "JPEG", quality=95)
    return output_path

def apply_ken_burns(img, frame_idx, total_frames, direction="zoom_in"):
    """Apply Ken Burns zoom effect"""
    w, h = img.size
    max_zoom = 0.2  # 20% zoom

    progress = frame_idx / max(total_frames - 1, 1)

    if direction == "zoom_in":
        scale = 1.0 + max_zoom * progress
    else:
        scale = 1.0 + max_zoom * (1 - progress)

    new_w = int(SHORTS_WIDTH * scale)
    new_h = int(SHORTS_HEIGHT * scale)

    # Crop center
    left = (w - new_w) // 2
    top = (h - new_h) // 2
    left = max(0, left)
    top = max(0, top)

    cropped = img.crop((left, top, left + min(new_w, w), top + min(new_h, h)))
    return cropped.resize((SHORTS_WIDTH, SHORTS_HEIGHT), Image.LANCZOS)

def draw_caption(frame_img, word, font_path=FONT_PATH):
    """Draw caption that auto-fits within frame width"""
    draw = ImageDraw.Draw(frame_img)
    word = word.upper()

    # Auto-shrink font size to fit 88% of frame width
    max_width = int(SHORTS_WIDTH * 0.88)
    font_size = 90
    font = ImageFont.load_default()
    while font_size > 30:
        try:
            font = ImageFont.truetype(font_path, font_size)
            bbox = draw.textbbox((0, 0), word, font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                break
        except:
            break
        font_size -= 5

    bbox = draw.textbbox((0, 0), word, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (SHORTS_WIDTH - text_w) // 2
    y = int(SHORTS_HEIGHT * 0.62) - text_h // 2

    # Thick shadow - no background box
    for dx, dy in [(-4,-4),(4,-4),(-4,4),(4,4),(-6,0),(6,0),(0,-6),(0,6)]:
        draw.text((x+dx, y+dy), word, font=font, fill=(0, 0, 0))

    # Bright yellow text
    draw.text((x, y), word, font=font, fill=(255, 220, 0))
    return frame_img

def create_video():
    audio_path = "output/voice.mp3"
    srt_path = "output/captions.srt"
    music_path = "assets/music/background.wav"

    duration = get_audio_duration(audio_path)
    print(f"Duration: {round(duration, 1)}s")

    images = get_background_images()
    if not images:
        raise FileNotFoundError("No background images found.")

    captions = parse_srt(srt_path)

    os.makedirs("output/frames", exist_ok=True)
    for f in glob.glob("output/frames/*.jpg"):
        os.remove(f)

    fps = 24
    total_frames = int(duration * fps)
    n = len(images)
    per_image_frames = total_frames // n

    print("Resizing background images...")
    resized_imgs = []
    for i, img_path in enumerate(images):
        out = f"output/bg_{i}.jpg"
        resize_image(img_path, out)
        resized_imgs.append(Image.open(out).convert("RGB"))

    # Word lookup
    frame_word = {}
    for start, end, word in captions:
        for f in range(int(start * fps), int(end * fps)):
            frame_word[f] = word

    # Alternate zoom directions per image
    directions = ["zoom_in", "zoom_out"]

    print("Rendering frames with Ken Burns effect...")
    for frame_idx in range(total_frames):
        bg_idx = min(frame_idx // per_image_frames, n - 1)
        local_frame = frame_idx - bg_idx * per_image_frames
        direction = directions[bg_idx % 2]

        frame = apply_ken_burns(resized_imgs[bg_idx], local_frame, per_image_frames, direction)

        word = frame_word.get(frame_idx)
        if word:
            frame = draw_caption(frame, word)

        frame.save(f"output/frames/{frame_idx:06d}.jpg", "JPEG", quality=80)

    print("Creating video...")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"output/video_{timestamp}.mp4"

    # Check if background music exists
    has_music = os.path.exists(music_path)

    if has_music:
        cmd = [
            get_ffmpeg(), "-y",
            "-framerate", str(fps),
            "-i", "output/frames/%06d.jpg",
            "-i", audio_path,
            "-i", music_path,
            "-filter_complex", "[1:a]volume=1.0[voice];[2:a]volume=0.15[music];[voice][music]amix=inputs=2:duration=first[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-threads", "1",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-shortest",
            output_path
        ]
    else:
        cmd = [
            get_ffmpeg(), "-y",
            "-framerate", str(fps),
            "-i", "output/frames/%06d.jpg",
            "-i", audio_path,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-threads", "1",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-shortest",
            output_path
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("FFMPEG ERROR:", result.stderr[-500:])
        raise RuntimeError("ffmpeg failed")

    latest_path = "output/final_video.mp4"
    shutil.copy(output_path, latest_path)
    print(f"Video ready: {output_path}")
    return latest_path
