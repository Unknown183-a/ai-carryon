# agents/video_agent.py
import os
import glob
import shutil
import datetime
import subprocess
import json

SHORTS_WIDTH = 1080
SHORTS_HEIGHT = 1920
SHORTS_MAX_DURATION = 60


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


def resize_image(image_path, output_path):
    """Resize image to 1080x1920 using ffmpeg"""
    cmd = [
        "ffmpeg", "-y",
        "-i", image_path,
        "-vf", f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=increase,crop={SHORTS_WIDTH}:{SHORTS_HEIGHT}",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def get_audio_duration(audio_path):
    """Get audio duration using moviepy"""
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


def create_slideshow(images, duration, output_path):
    """Create slideshow video from images using ffmpeg"""
    n = len(images)
    per_image = duration / n

    # Resize all images first
    resized = []
    for i, img in enumerate(images):
        out = f"/tmp/slide_{i}.jpg"
        resize_image(img, out)
        resized.append(out)

    # Create input file list for ffmpeg
    list_path = "/tmp/images.txt"
    with open(list_path, "w") as f:
        for img in resized:
            f.write(f"file '{img}'\n")
            f.write(f"duration {per_image}\n")
        # Last image needs to be listed twice for ffmpeg
        f.write(f"file '{resized[-1]}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-vf", f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT},zoompan=z='min(zoom+0.0015,1.5)':d=1:s={SHORTS_WIDTH}x{SHORTS_HEIGHT}",
        "-c:v", "libx264",
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def add_captions_ffmpeg(video_path, srt_path, output_path):
    """Burn word-by-word captions into video using ffmpeg drawtext"""
    captions = parse_srt(srt_path)

    # Build drawtext filter for each word
    filters = []
    for start, end, word in captions:
        # Escape special characters
        word_escaped = word.upper().replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")
        
        filter_str = (
            f"drawtext=text='{word_escaped}'"
            f":fontsize=90"
            f":fontcolor=yellow"
            f":borderw=5"
            f":bordercolor=black"
            f":x=(w-text_w)/2"
            f":y=(h*0.6)-text_h/2"
            f":enable='between(t,{start:.3f},{end:.3f})'"
        )
        filters.append(filter_str)

    # Combine all filters
    vf = ",".join(filters)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-c:a", "copy",
        "-pix_fmt", "yuv420p",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def create_video():
    audio_path = "output/voice.mp3"
    srt_path = "output/captions.srt"

    duration = get_audio_duration(audio_path)

    if duration > SHORTS_MAX_DURATION:
        print(f"WARNING: Audio is {duration:.1f}s — over 60s Shorts limit!")
    else:
        print(f"Duration: {duration:.1f}s — Shorts ready!")

    images = get_background_images()
    if not images:
        raise FileNotFoundError("No background images found.")

    os.makedirs("output", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Step 1: Create slideshow
    print("Creating slideshow...")
    slideshow_path = f"/tmp/slideshow_{timestamp}.mp4"
    create_slideshow(images, duration, slideshow_path)

    # Step 2: Add audio
    print("Adding audio...")
    with_audio_path = f"/tmp/with_audio_{timestamp}.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-i", slideshow_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        with_audio_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    # Step 3: Add captions
    print("Adding captions...")
    output_path = f"output/video_{timestamp}.mp4"
    add_captions_ffmpeg(with_audio_path, srt_path, output_path)

    # Copy to latest
    latest_path = "output/final_video.mp4"
    shutil.copy(output_path, latest_path)

    print(f"Video ready: {output_path}")
    return latest_path
