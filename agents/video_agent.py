# agents/video_agent.py
import os
import glob
import shutil
import datetime
import subprocess


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
    w = str(SHORTS_WIDTH)
    h = str(SHORTS_HEIGHT)
    vf = "scale=" + w + ":" + h + ":force_original_aspect_ratio=increase,crop=" + w + ":" + h
    cmd = ["ffmpeg", "-y", "-i", image_path, "-vf", vf, output_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def create_slideshow(images, duration, output_path):
    n = len(images)
    per_image = duration / n
    resized = []
    for i, img in enumerate(images):
        out = "/tmp/slide_" + str(i) + ".jpg"
        resize_image(img, out)
        resized.append(out)

    list_path = "/tmp/images.txt"
    with open(list_path, "w") as f:
        for img in resized:
            f.write("file " + repr(img) + "\n")
            f.write("duration " + str(per_image) + "\n")
        f.write("file " + repr(resized[-1]) + "\n")

    w = str(SHORTS_WIDTH)
    h = str(SHORTS_HEIGHT)
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", list_path,
        "-vf", "scale=" + w + ":" + h,
        "-c:v", "libx264", "-r", "30",
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def build_drawtext_filter(captions):
    parts = []
    for start, end, word in captions:
        w = word.upper()
        w = w.replace("\\", "")
        w = w.replace("'", "")
        w = w.replace(":", " ")
        w = w.replace(",", " ")
        w = w.replace("$", "")
        w = w.replace("%", " PCT")
        
        start_s = "{:.3f}".format(start)
        end_s = "{:.3f}".format(end)
        
        # Build y expression using multiplication
        y = "h" + chr(42) + "0.6-text_h/2"
        
        part = (
            "drawtext=text='" + w + "'"
            + ":fontsize=90"
            + ":fontcolor=yellow"
            + ":borderw=5"
            + ":bordercolor=black"
            + ":x=(w-text_w)/2"
            + ":y=" + y
            + ":enable='between(t," + start_s + "," + end_s + ")'"
        )
        parts.append(part)
    
    return ",".join(parts)


def create_video():
    audio_path = "output/voice.mp3"
    srt_path = "output/captions.srt"

    duration = get_audio_duration(audio_path)
    print("Duration: " + str(round(duration, 1)) + "s")

    images = get_background_images()
    if not images:
        raise FileNotFoundError("No background images found.")

    os.makedirs("output", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    print("Creating slideshow...")
    slideshow_path = "/tmp/slideshow_" + timestamp + ".mp4"
    create_slideshow(images, duration, slideshow_path)

    print("Adding audio...")
    with_audio_path = "/tmp/with_audio_" + timestamp + ".mp4"
    cmd = [
        "ffmpeg", "-y",
        "-i", slideshow_path,
        "-i", audio_path,
        "-c:v", "copy", "-c:a", "aac",
        "-shortest", with_audio_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    print("Adding captions...")
    captions = parse_srt(srt_path)
    vf = build_drawtext_filter(captions)

    output_path = "output/video_" + timestamp + ".mp4"
    # Write filter to file to avoid shell escaping issues
    filter_file = "/tmp/filter_" + timestamp + ".txt"
    with open(filter_file, "w") as ff:
        ff.write(vf)
    
    cmd = [
        "ffmpeg", "-y",
        "-i", with_audio_path,
        "-filter_script:v", filter_file,
        "-c:v", "libx264",
        "-c:a", "copy",
        "-pix_fmt", "yuv420p",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    latest_path = "output/final_video.mp4"
    shutil.copy(output_path, latest_path)
    print("Video ready: " + output_path)
    return latest_path
