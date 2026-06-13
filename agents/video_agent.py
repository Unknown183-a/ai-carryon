# agents/video_agent.py
from moviepy import *
import os
import glob
import shutil
import datetime
import json

FONT_PATH = "assets/fonts/Arial-Bold.ttf"


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

    voice = AudioFileClip(audio_path)
    duration = voice.duration

    # --- Background images fast cuts ---
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

    layers = [bg]

    # --- Yellow highlight captions ---
    words_path = "output/captions_words.json"

    if os.path.exists(words_path):
        with open(words_path) as f:
            word_entries = json.load(f)

        for entry in word_entries:
            start = entry["start"]
            end = entry["end"]
            before = entry["before"].upper()
            current = entry["current"].upper()
            after = entry["after"].upper()

            if before and after:
                display = f"{before} {current} {after}"
            elif before:
                display = f"{before} {current}"
            elif after:
                display = f"{current} {after}"
            else:
                display = current

            # Single clip - yellow for current word only
            # Build line: before(white) + CURRENT(yellow) + after(white)
            # Use only current word highlighted, show 4-word chunk as context
            # Render just the current word in yellow, full line in white behind
            
            # Show only current word in yellow (clean, no overlap)
            txt = (
                TextClip(
                    text=display,
                    font_size=85,
                    color="#FFD700",
                    stroke_color="black",
                    stroke_width=3,
                    size=(900, None),
                    method="caption",
                    font=FONT_PATH
                )
                .with_position(("center", "center"))
                .with_start(start)
                .with_end(end)
            )
            layers.append(txt)
    else:
        # Fallback regular captions
        captions = parse_srt(srt_path)
        for start, end, text in captions:
            txt = (
                TextClip(
                    text=text.upper(),
                    font_size=85,
                    color="#FFD700",
                    stroke_color="black",
                    stroke_width=3,
                    size=(900, None),
                    method="caption",
                    font=FONT_PATH
                )
                .with_position(("center", "center"))
                .with_start(start)
                .with_end(end)
            )
            layers.append(txt)

    # --- Background music ---
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

    # --- Final ---
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
