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

def get_background_clips():
    """Get uploaded Flow/Veo MP4 clips from assets/flow_clips/"""
    folder = "assets/flow_clips"
    clips = []
    if os.path.isdir(folder):
        for ext in ("*.mp4", "*.mov", "*.webm"):
            clips.extend(glob.glob(os.path.join(folder, ext)))
    clips.sort()
    return clips


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
    img = img.resize((int(SHORTS_WIDTH * 1.3), int(SHORTS_HEIGHT * 1.3)), Image.LANCZOS)
    img.save(output_path, "JPEG", quality=95)
    return output_path

def apply_ken_burns(img, frame_idx, total_frames, direction="zoom_in"):
    w, h = img.size
    max_zoom = 0.2
    progress = frame_idx / max(total_frames - 1, 1)
    if direction == "zoom_in":
        scale = 1.0 + max_zoom * progress
    else:
        scale = 1.0 + max_zoom * (1 - progress)
    new_w = int(SHORTS_WIDTH * scale)
    new_h = int(SHORTS_HEIGHT * scale)
    left = max(0, (w - new_w) // 2)
    top = max(0, (h - new_h) // 2)
    cropped = img.crop((left, top, left + min(new_w, w), top + min(new_h, h)))
    return cropped.resize((SHORTS_WIDTH, SHORTS_HEIGHT), Image.LANCZOS)

def draw_caption(frame_img, text, font_path=FONT_PATH):
    draw = ImageDraw.Draw(frame_img)
    text = text.upper()
    max_width = int(SHORTS_WIDTH * 0.88)
    font_size = 95
    font = ImageFont.load_default()
    while font_size > 30:
        try:
            font = ImageFont.truetype(font_path, font_size)
            bbox = draw.textbbox((0, 0), text, font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                break
        except:
            break
        font_size -= 5

    # Word wrap if still too wide
    words = text.split()
    lines = []
    current = ""
    for w in words:
        test = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = w
        else:
            current = test
    if current:
        lines.append(current)

    line_height = font_size + 10
    total_h = len(lines) * line_height
    y = int(SHORTS_HEIGHT * 0.65) - total_h // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (SHORTS_WIDTH - text_w) // 2
        # Black shadow
        for dx, dy in [(-4,-4),(4,-4),(-4,4),(4,4),(-6,0),(6,0),(0,-6),(0,6)]:
            draw.text((x+dx, y+dy), line, font=font, fill=(0, 0, 0))
        # Yellow text
        draw.text((x, y), line, font=font, fill=(255, 220, 0))
        y += line_height

    return frame_img

def extract_manim_frames(manim_path, total_frames, fps):
    print("Extracting Manim frames...")
    frames_dir = "output/manim_frames"
    os.makedirs(frames_dir, exist_ok=True)
    for f in glob.glob(f"{frames_dir}/*.jpg"):
        os.remove(f)
    cmd = [
        get_ffmpeg(), "-y",
        "-i", manim_path,
        "-vf", f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=decrease,pad={SHORTS_WIDTH}:{SHORTS_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
        "-q:v", "2",
        f"{frames_dir}/%06d.jpg"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Frame extraction failed:", result.stderr[-300:])
        return None
    extracted = sorted(glob.glob(f"{frames_dir}/*.jpg"))
    if not extracted:
        return None
    print(f"Extracted {len(extracted)} Manim frames")
    looped = []
    while len(looped) < total_frames:
        looped.extend(extracted)
    return looped[:total_frames]


def _create_video_from_clips(clip_paths, audio_path, srt_path, manim_path=None):
    """Stitch Flow/Veo MP4 clips with clips own audio"""
    ffmpeg = get_ffmpeg()
    os.makedirs("output", exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"output/video_{timestamp}.mp4"

    audio_duration = get_audio_duration(audio_path)
    print(f"Target duration: {audio_duration:.1f}s, clips: {len(clip_paths)}")

    # Step 1 — write concat file
    concat_path = "output/flow_concat.txt"
    with open(concat_path, "w") as f:
        for cp in clip_paths:
            f.write("file '" + os.path.abspath(cp) + "'\n")

    # Step 2 — concat clips with audio intact (no re-encode video, copy streams)
    concat_video = "output/flow_concat_raw.mp4"
    log1 = open("output/ffmpeg_step1.log", "w")
    ret = subprocess.call([
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_path,
        "-t", str(audio_duration),
        "-c", "copy",
        concat_video
    ], stdout=log1, stderr=log1)
    log1.close()
    if ret != 0:
        raise RuntimeError("Concat clips failed: " + open("output/ffmpeg_step1.log").read()[-300:])

    # Step 3 — scale video to shorts dimensions
    scaled_video = "output/flow_scaled.mp4"
    log2 = open("output/ffmpeg_step2.log", "w")
    ret = subprocess.call([
        ffmpeg, "-y",
        "-i", concat_video,
        "-vf", f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=increase,crop={SHORTS_WIDTH}:{SHORTS_HEIGHT}",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        scaled_video
    ], stdout=log2, stderr=log2)
    log2.close()
    if ret != 0:
        raise RuntimeError("Scale failed: " + open("output/ffmpeg_step2.log").read()[-300:])

    import shutil
    shutil.copy(scaled_video, output_path)
    latest = "output/final_video.mp4"
    shutil.copy(output_path, latest)
    print(f"Flow video ready: {output_path}")
    return latest


def _create_video_from_clips_UNUSED(clip_paths, audio_path, srt_path, manim_path=None):
    """OLD — frame-by-frame method, kept for reference"""
    ffmpeg = get_ffmpeg()
    os.makedirs("output/frames", exist_ok=True)
    for f in glob.glob("output/frames/*.jpg"):
        os.remove(f)
    audio_duration = get_audio_duration(audio_path)
    fps = 24
    total_frames = int(audio_duration * fps)
    captions = parse_srt(srt_path) if os.path.exists(srt_path) else []
    frames_needed = total_frames
    looped_clips = []
    while len(looped_clips) < frames_needed // (fps * 8) + len(clip_paths):
        looped_clips.extend(clip_paths)
    frames_per_clip = total_frames // len(clip_paths)
    frame_idx = 0
    for clip_i, clip_path in enumerate(looped_clips):
        if frame_idx >= total_frames:
            break
        clip_frames_dir = f"output/frames/clip_{clip_i}"
        os.makedirs(clip_frames_dir, exist_ok=True)
        extract_cmd = [
            ffmpeg, "-y", "-i", clip_path,
            "-vf", f"fps={fps},scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=increase,crop={SHORTS_WIDTH}:{SHORTS_HEIGHT}",
            "-q:v", "2", f"{clip_frames_dir}/frame_%04d.jpg"
        ]
        subprocess.run(extract_cmd, capture_output=True)
        extracted = sorted(glob.glob(f"{clip_frames_dir}/frame_*.jpg"))
        if not extracted:
            continue
        remaining = total_frames - frame_idx
        n_frames = min(frames_per_clip, remaining)
        for i in range(n_frames):
            src_frame = extracted[i % len(extracted)]
            img = Image.open(src_frame).convert("RGB")
            img = img.resize((SHORTS_WIDTH, SHORTS_HEIGHT), Image.LANCZOS)
            out_path = f"output/frames/{frame_idx:06d}.jpg"
            img.save(out_path, "JPEG", quality=85)
            frame_idx += 1
    os.makedirs("output", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"output/video_{timestamp}.mp4"
    cmd = [
        ffmpeg, "-y",
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
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-500:]}")

    latest = "output/final_video.mp4"
    shutil.copy(output_path, latest)
    print(f"Video ready: {output_path}")
    return latest


def extract_frames_from_clip(clip_path, target_fps=24):
    """Extract frames from an MP4 clip using ffmpeg"""
    import tempfile, json
    ffmpeg = get_ffmpeg()

    # Get clip duration
    probe_cmd = [ffmpeg.replace("ffmpeg", "ffprobe"), "-v", "quiet",
                 "-print_format", "json", "-show_streams", clip_path]
    try:
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        info = json.loads(result.stdout)
        duration = float(info["streams"][0]["duration"])
    except Exception:
        duration = 8.0

    return duration


def create_video(manim_path=None):
    audio_path = "output/voice.mp3"
    srt_path = "output/captions.srt"

    # Check for Flow/Veo MP4 clips first
    flow_clips = get_background_clips()
    if flow_clips:
        print(f"Using {len(flow_clips)} Flow clips as background")
        return _create_video_from_clips(flow_clips, audio_path, srt_path, manim_path)
    music_path = "assets/music/background.wav"

    duration = get_audio_duration(audio_path)
    print(f"Duration: {round(duration, 1)}s")

    captions = parse_srt(srt_path)

    os.makedirs("output/frames", exist_ok=True)
    for f in glob.glob("output/frames/*.jpg"):
        os.remove(f)

    fps = 24
    total_frames = int(duration * fps)

    frame_word = {}
    for start, end, word in captions:
        for fi in range(int(start * fps), int(end * fps)):
            frame_word[fi] = word

    use_manim = False
    if manim_path and os.path.exists(manim_path):
        manim_frames = extract_manim_frames(manim_path, total_frames, fps)
        if manim_frames:
            use_manim = True
            print("Rendering frames with Manim background + captions...")
            for frame_idx in range(total_frames):
                frame = Image.open(manim_frames[frame_idx]).convert("RGB")
                frame = frame.resize((SHORTS_WIDTH, SHORTS_HEIGHT), Image.LANCZOS)
                overlay = Image.new("RGBA", (SHORTS_WIDTH, SHORTS_HEIGHT), (0, 0, 0, 60))
                frame = Image.alpha_composite(frame.convert("RGBA"), overlay).convert("RGB")
                word = frame_word.get(frame_idx)
                if word:
                    frame = draw_caption(frame, word)
                frame.save(f"output/frames/{frame_idx:06d}.jpg", "JPEG", quality=80)

    if not use_manim:
        print("Using background images...")
        images = get_background_images()
        if not images:
            raise FileNotFoundError("No background images found.")
        resized_imgs = []
        for i, img_path in enumerate(images):
            out = f"output/bg_{i}.jpg"
            resize_image(img_path, out)
            resized_imgs.append(Image.open(out).convert("RGB"))
        n = len(images)
        per_image_frames = total_frames // n
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

    print("Creating video with ffmpeg...")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"output/video_{timestamp}.mp4"
    has_music = os.path.exists(music_path)

    if has_music:
        cmd = [
            get_ffmpeg(), "-y",
            "-framerate", str(fps),
            "-i", "output/frames/%06d.jpg",
            "-i", audio_path,
            "-i", music_path,
            "-filter_complex", "[1:a]volume=1.0[voice];[2:a]volume=0.15[music];[voice][music]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-threads", "1", "-c:a", "aac",
            "-pix_fmt", "yuv420p", "-shortest", output_path
        ]
    else:
        cmd = [
            get_ffmpeg(), "-y",
            "-framerate", str(fps),
            "-i", "output/frames/%06d.jpg",
            "-i", audio_path,
            "-c:v", "libx264", "-preset", "ultrafast",
            "-threads", "1", "-c:a", "aac",
            "-pix_fmt", "yuv420p", "-shortest", output_path
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("FFMPEG ERROR:", result.stderr[-500:])
        raise RuntimeError("ffmpeg failed")

    latest_path = "output/final_video.mp4"
    shutil.copy(output_path, latest_path)
    print(f"Video ready: {output_path}")
    return latest_path
