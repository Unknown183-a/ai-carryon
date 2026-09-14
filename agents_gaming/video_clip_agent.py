# agents_gaming/video_clip_agent.py
"""
Downloads the actual Twitch clip as background footage for the Short.

This is the one piece that's genuinely different from every other channel
in this repo: English/Hindi/Cricket all render over STOCK footage (Pexels)
or static images because there's no single "the video" for an abstract
topic or a cricket match. Gaming is the opposite — the clip itself already
IS the perfect vertical(ish) footage, so we download it directly instead of
searching for something topic-relevant.

Helix doesn't hand back a raw downloadable file URL for clips (deliberately,
per their ToS ambiguity around clip re-hosting), so this shells out to
yt-dlp — the same tool the ecosystem generally relies on for this — pointed
at the clip's public `url` field from Twitch.

Once downloaded, the clip is handed to agents.video_agent's EXISTING
_create_video_from_pexels_clips() renderer unchanged — that function only
cares that it received a list of local mp4 paths, not where they came from.
"""
import os
import subprocess


def download_twitch_clip(clip, output_path):
    """clip: a raw Helix clip dict (has 'url', 'id'). Returns output_path."""
    clip_url = clip.get("url")
    if not clip_url:
        raise RuntimeError("Clip has no 'url' field to download")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--format", "best",  # Twitch clips are short, single-file mp4 already
        "--output", output_path,
        clip_url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError(f"yt-dlp failed for {clip_url}: {result.stderr[-500:]}")

    return output_path


def get_gaming_background_clip(clip):
    """Returns a list with one local mp4 path (matches the list-of-paths
    shape _create_video_from_pexels_clips expects). A single real clip
    beats several unrelated stock clips — that IS the highlight."""
    folder = "assets/gaming_clips"
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))

    output_path = os.path.join(folder, f"{clip.get('id', 'clip')}.mp4")
    download_twitch_clip(clip, output_path)
    return [output_path]
