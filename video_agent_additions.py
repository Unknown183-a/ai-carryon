
# ============================================================
# Additions for Pexels dynamic video clips (append to video_agent.py)
# ============================================================

def get_pexels_clips():
    """Get downloaded Pexels stock video clips from assets/pexels_clips/"""
    folder = "assets/pexels_clips"
    clips = []
    if os.path.isdir(folder):
        for ext in ("*.mp4", "*.mov", "*.webm"):
            clips.extend(glob.glob(os.path.join(folder, ext)))
    clips.sort()
    return clips


def _caption_force_style():
    # Mirrors the previous PIL caption style: big bold yellow text,
    # black outline, positioned around 65% down the frame.
    return (
        "FontName=DejaVu Sans Bold,FontSize=78,"
        "PrimaryColour=&H00DCFF&,OutlineColour=&H000000&,"
        "BorderStyle=1,Outline=4,Shadow=0,Alignment=2,MarginV=650,Bold=1"
    )


def _create_video_from_pexels_clips(clip_paths, audio_path, srt_path, music_path=None):
    """
    Stitch topic-relevant Pexels stock clips as silent B-roll, scaled/cropped
    to fill the Shorts frame, trimmed/looped to match the TTS voiceover's
    exact duration — then attach the real voiceover (+ optional background
    music) and burn in captions from the SRT. Unlike _create_video_from_clips
    (built for self-contained AI-generated clips), this path always uses OUR
    voiceover audio, never the stock clip's own audio track.
    """
    ffmpeg = get_ffmpeg()
    os.makedirs("output", exist_ok=True)

    audio_duration = get_audio_duration(audio_path)
    n = len(clip_paths)
    per_clip = audio_duration / n
    print(f"Target duration: {audio_duration:.1f}s across {n} Pexels clips (~{per_clip:.1f}s each)")

    segment_paths = []
    for i, clip_path in enumerate(clip_paths):
        seg_path = f"output/pexels_seg_{i}.mp4"
        cmd = [
            ffmpeg, "-y",
            "-stream_loop", "-1",   # loop the source clip if it's shorter than needed
            "-i", clip_path,
            "-t", str(per_clip),
            "-vf", f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=increase,"
                   f"crop={SHORTS_WIDTH}:{SHORTS_HEIGHT},setsar=1,fps=30",
            "-an",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-pix_fmt", "yuv420p",
            seg_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Segment {i} trim failed, skipping: {result.stderr[-300:]}")
            continue
        segment_paths.append(seg_path)

    if not segment_paths:
        raise RuntimeError("All Pexels clip segments failed to render.")

    concat_path = "output/pexels_concat.txt"
    with open(concat_path, "w") as f:
        for sp in segment_paths:
            f.write("file '" + os.path.abspath(sp) + "'\n")

    silent_bg = "output/pexels_bg_silent.mp4"
    concat_cmd = [
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_path,
        "-t", str(audio_duration),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p",
        silent_bg
    ]
    result = subprocess.run(concat_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Pexels concat failed: {result.stderr[-500:]}")

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"output/video_{timestamp}.mp4"
    has_music = music_path and os.path.exists(music_path)
    has_captions = srt_path and os.path.exists(srt_path)

    vf = f"subtitles={srt_path}:force_style='{_caption_force_style()}'" if has_captions else None

    if has_music:
        filter_complex = "[1:a]volume=1.0[voice];[2:a]volume=0.15[music];[voice][music]amix=inputs=2:duration=first[aout]"
        cmd = [ffmpeg, "-y", "-i", silent_bg, "-i", audio_path, "-i", music_path]
        if vf:
            cmd += ["-filter_complex", filter_complex, "-vf", vf]
        else:
            cmd += ["-filter_complex", filter_complex]
        cmd += [
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac", "-pix_fmt", "yuv420p", "-shortest", output_path
        ]
    else:
        cmd = [ffmpeg, "-y", "-i", silent_bg, "-i", audio_path]
        if vf:
            cmd += ["-vf", vf]
        cmd += [
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac", "-pix_fmt", "yuv420p", "-shortest", output_path
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and has_captions:
        # Caption burn (subtitles filter needs libass) may not be supported
        # by every ffmpeg build — retry once without captions rather than
        # failing the whole video.
        print(f"Caption burn failed, retrying without captions: {result.stderr[-400:]}")
        cmd = [c for c in cmd if not (isinstance(c, str) and c.startswith("subtitles="))]
        if "-vf" in cmd:
            vf_idx = cmd.index("-vf")
            del cmd[vf_idx:vf_idx + 2]
        result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Pexels final render failed: {result.stderr[-500:]}")

    latest = "output/final_video.mp4"
    shutil.copy(output_path, latest)
    print(f"Pexels clip video ready: {output_path}")
    return latest
