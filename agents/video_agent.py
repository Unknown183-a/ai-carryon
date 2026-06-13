# agents/video_agent.py
from moviepy import *
import numpy as np
import os
import glob
import shutil
import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
FONT_PATH = "assets/fonts/Arial-Bold.ttf"


def fetch_person_video(duration):
    """Fetch a free talking person video from Pexels"""
    headers = {"Authorization": PEXELS_API_KEY}
    
    # Search for person talking videos
    queries = ["person talking", "woman explaining", "man presenting tech"]
    
    for query in queries:
        url = f"https://api.pexels.com/videos/search?query={query}&orientation=portrait&per_page=10&min_duration=5"
        response = requests.get(url, headers=headers, timeout=30)
        data = response.json()
        videos = data.get("videos", [])
        
        if videos:
            # Pick random video
            import random
            video = random.choice(videos)
            # Get best quality file
            files = sorted(video["video_files"], 
                         key=lambda x: x.get("width", 0), reverse=True)
            video_url = files[0]["link"]
            
            # Download it
            os.makedirs("assets/person", exist_ok=True)
            path = "assets/person/presenter.mp4"
            r = requests.get(video_url, timeout=60)
            with open(path, "wb") as f:
                f.write(r.content)
            return path
    
    return None


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
    font_path = FONT_PATH

    voice = AudioFileClip(audio_path)
    duration = voice.duration

    # --- Background images (top 60% of screen) ---
    images = get_background_images()
    if not images:
        raise FileNotFoundError("No background images found.")

    cut_duration = 3.0
    needed = int(duration / cut_duration) + 1
    images_looped = (images * (needed // len(images) + 1))[:needed]

    bg_clips = []
    for img_path in images_looped:
        clip = ImageClip(img_path).with_duration(cut_duration)
        clip = clip.resized((1080, 1920))
        overlay = ColorClip(
            size=(1080, 1920),
            color=[0, 0, 0]
        ).with_duration(cut_duration).with_opacity(0.55)
        bg_clips.append(CompositeVideoClip([clip, overlay]))

    bg = concatenate_videoclips(bg_clips, method="compose").subclipped(0, duration)

    # --- Person video (bottom 40% of screen) ---
    layers = [bg]
    
    person_path = "assets/person/presenter.mp4"
    
    # Download fresh person video if not exists
    if not os.path.exists(person_path):
        print("Fetching presenter video from Pexels...")
        person_path = fetch_person_video(duration)

    if person_path and os.path.exists(person_path):
        person_clip = VideoFileClip(person_path)
        
        # Loop if shorter than duration
        if person_clip.duration < duration:
            loops = int(duration / person_clip.duration) + 1
            person_clip = concatenate_videoclips([person_clip] * loops)
        
        person_clip = person_clip.subclipped(0, duration)
        
        # Resize to full width, place at bottom
        person_clip = person_clip.resized(width=1080)
        person_h = int(1920 * 0.45)  # 45% of screen height
        person_clip = person_clip.resized((1080, person_h))
        person_clip = person_clip.with_position(("center", 1920 - person_h))
        
        # Dark gradient overlay on top of person (blend with bg)
        grad = ColorClip(
            size=(1080, 120),
            color=[0, 0, 0]
        ).with_duration(duration).with_opacity(0.8)
        grad = grad.with_position(("center", 1920 - person_h))
        
        layers.append(person_clip)
        layers.append(grad)

    # --- Word-by-word captions (middle of screen) ---
    captions = parse_srt(srt_path)
    for start, end, text in captions:
        txt = (
            TextClip(
                text=text.upper(),
                font_size=85,
                color="white",
                stroke_color="black",
                stroke_width=3,
                size=(900, None),
                method="caption",
                font=font_path
            )
            .with_position(("center", 0.45), relative=True)
            .with_start(start)
            .with_end(end)
        )
        layers.append(txt)

    # --- Background music ---
    audio_clips = [voice]
    music_path = "assets/music/bg_music.mp3"
    if os.path.exists(music_path):
        try:
            music = AudioFileClip(music_path).subclipped(0, duration)
            music = music.with_effects([afx.MultiplyVolume(0.12)])
            final_audio = CompositeAudioClip([voice, music])
        except:
            final_audio = voice
    else:
        final_audio = voice

    # --- Final composite ---
    final = CompositeVideoClip(layers).with_audio(final_audio)

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
