# agents/video_clip_agent.py
"""
Fetches topic-relevant vertical video clips from Pexels' Videos API
(free, same API key as Pexels Photos — https://www.pexels.com/api/)
to use as dynamic B-roll instead of static Ken-Burns images.

Falls back gracefully: if a search term returns nothing, or the
Pexels video endpoint errors out, that slot is just skipped — the
caller (scheduler.py) falls back to generate_backgrounds() (static
images) if this returns too few clips to make a decent video.
"""
import os
import re
import requests

from agents.image_agent import generate_image_prompts  # reuse existing LLM prompt generation


def _pick_best_video_file(video_files):
    """
    Pexels returns several encodes per clip (different widths/qualities).
    Prefer something close to 720-1080px wide — good visual quality for
    Shorts without downloading an oversized 4K file every time.
    """
    if not video_files:
        return None
    candidates = [f for f in video_files if f.get("file_type") == "video/mp4"]
    if not candidates:
        candidates = video_files
    candidates.sort(key=lambda f: abs((f.get("width") or 0) - 1080))
    return candidates[0]["link"]


def search_pexels_video(query, min_duration=3, max_duration=25):
    pexels_key = os.getenv("PEXELS_API_KEY", "")
    if not pexels_key:
        return None
    headers = {"Authorization": pexels_key}
    params = {
        "query": query,
        "orientation": "portrait",
        "size": "medium",
        "per_page": 1,
        "min_duration": min_duration,
        "max_duration": max_duration,
    }
    r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    videos = data.get("videos", [])
    if not videos:
        return None
    return _pick_best_video_file(videos[0].get("video_files", []))


def download_video_clip(prompt, output_path):
    clean_prompt = re.sub(r"[^a-zA-Z0-9 ,]", "", prompt).strip()
    search_query = " ".join(clean_prompt.split()[:5])

    video_url = search_pexels_video(search_query)
    if not video_url:
        # Retry once with a shorter, broader query (e.g. just the first 2 words)
        broad_query = " ".join(clean_prompt.split()[:2])
        if broad_query != search_query:
            video_url = search_pexels_video(broad_query)

    if not video_url:
        raise RuntimeError(f"No Pexels video found for query: '{search_query}'")

    resp = requests.get(video_url, timeout=90, stream=True)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
    return output_path


def generate_background_clips(topic, script, num_clips=4):
    folder = "assets/pexels_clips"
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))

    clean_topic = topic.split("||PATTERN:")[0].strip()
    prompts = generate_image_prompts(clean_topic, script, num_clips)

    print(f"\nSearching Pexels video clips for: {clean_topic}")
    for i, p in enumerate(prompts):
        print(f"  {i+1}: {p}")

    clip_paths = []
    errors = []
    for i, prompt in enumerate(prompts):
        output_path = os.path.join(folder, f"{i+1}.mp4")
        try:
            download_video_clip(prompt, output_path)
            clip_paths.append(output_path)
            print(f"Clip {i+1}: downloaded")
        except Exception as e:
            errors.append(f"Clip {i+1}: {e}")
            print(f"Clip {i+1} failed: {e}")

    return clip_paths, errors
