# agents/video_agent.py
import os
import glob
import shutil
import datetime
import subprocess
from PIL import Image, ImageDraw, ImageFont

SHORTS_WIDTH = 1080
SHORTS_HEIGHT = 1920
SHORTS_MAX_DURATION = 60
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


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
    img = img.resize((SHORTS_WIDTH, SHORTS_HEIGHT), Image.LANCZOS)
    img.save(output_path, "JPEG", quality=95)
    return output_path


def draw_word_on_frame(frame_img, word, font_path=FONT_PATH):
    """Draw a single word centered on the frame"""
    draw = ImageDraw.Draw(frame_img)
    try:
        font = ImageFont.truetype(font_path, 90)
    except:
        font = ImageFont.load_default()

    word = word.upper()
    bbox = draw.textbbox((0, 0), word, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (SHORTS_WIDTH - text_w) // 2
    y = int(SHORTS_HEIGHT * 0.6) - text_h // 2

    # Shadow
    for dx, dy in [(-3,-3),(3,-3),(-3,3),(3,3),(0,4),(4,0),(-4,0),(0,-4)]:
        draw.text((x+dx, y+dy), word, font=font, fill=(0,0,0))
    # Main text
    draw.text((x, y), word, font=font, fill=(255, 220, 0))
    return frame_img


def create_video():
    audio_path = "output/voice.mp3"
    srt_path = "output/captions.srt"

    duration = get_audio_duration(audio_path)
    print("Duration: " + str(round(duration, 1)) + "s")

    images = get_background_images()
    if not images:
        raise FileNotFoundError("No background images found.")

    captions = parse_srt(srt_path)

    os.makedirs("output", exist_ok=True)
    os.makedirs("/tmp/frames", exist_ok=True)

    # Clear old frames
    for f in glob.glob("/tmp/frames/*.jpg"):
        os.remove(f)

    fps = 24
    total_frames = int(duration * fps)
    n = len(images)
    per_image_frames = total_frames // n

    print("Rendering frames...")
    # Resize background images
    resized_imgs = []
    for i, img_path in enumerate(images):
        out = "/tmp/bg_" + str(i) + ".jpg"
        resize_image(img_path, out)
        resized_imgs.append(Image.open(out).convert("RGB"))

    # Build word lookup: frame -> word
    frame_word = {}
    for start, end, word in captions:
        start_frame = int(start * fps)
        end_frame = int(end * fps)
        for f in range(start_frame, end_frame):
            frame_word[f] = word

    # Render each frame
    for frame_idx in range(total_frames):
        bg_idx = min(frame_idx // per_image_frames, n - 1)
        frame = resized_imgs[bg_idx].copy()

        word = frame_word.get(frame_idx)
        if word:
            frame = draw_word_on_frame(frame, word)

        frame.save("/tmp/frames/" + str(frame_idx).zfill(6) + ".jpg", "JPEG", quality=90)

    print("Creating video from frames...")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = "output/video_" + timestamp + ".mp4"

    # Combine frames into video
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", "/tmp/frames/%06d.jpg",
        "-i", audio_path,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("FFMPEG ERROR:", result.stderr[-500:])
        raise RuntimeError("ffmpeg failed: " + result.stderr[-200:])

    latest_path = "output/final_video.mp4"
    shutil.copy(output_path, latest_path)
    print("Video ready: " + output_path)
    return latest_path
