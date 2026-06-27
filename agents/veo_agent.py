"""
agents/veo_agent.py — Automated video clip generation via Veo 3.1 API

Uses your existing GEMINI_API_KEY to generate 3 clips automatically.
Free tier: 50 requests/day via Google AI Studio.
Saves clips to assets/flow_clips/ — same folder the dashboard uses.

Usage:
    from agents.veo_agent import generate_clips
    paths = generate_clips(prompts)  # returns list of 3 mp4 paths
"""

import os
import time
import requests
import glob

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OUTPUT_DIR = "assets/flow_clips"
MODEL = "models/veo-3.1-lite-generate-preview"  # cheapest, fastest
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def generate_clips(prompts: list, aspect_ratio="9:16", duration=8) -> list:
    """
    Generate video clips from prompts using Veo 3.1 API.
    Returns list of saved MP4 file paths.
    Falls back gracefully if API fails.
    """
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY not set — skipping Veo generation")
        return []

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Clear old clips
    for f in glob.glob(f"{OUTPUT_DIR}/*.mp4"):
        os.remove(f)

    saved_paths = []

    for i, prompt in enumerate(prompts[:3]):
        print(f"Generating clip {i+1}/3 via Veo API...")
        try:
            path = _generate_single_clip(prompt, i, aspect_ratio, duration)
            if path:
                saved_paths.append(path)
                print(f"Clip {i+1} saved: {path}")
            else:
                print(f"Clip {i+1} failed — skipping")
        except Exception as e:
            print(f"Clip {i+1} error: {e}")
        time.sleep(2)  # respect rate limits

    return saved_paths


def _generate_single_clip(prompt: str, index: int, aspect_ratio: str, duration: int) -> str:
    """Submit generation request and poll until complete."""
    headers = {"Content-Type": "application/json"}
    url = f"{BASE_URL}/models/veo-3.1-lite-generate-preview:generateVideos?key={GEMINI_API_KEY}"

    payload = {
        "prompt": prompt,
        "generationConfig": {
            "aspectRatio": aspect_ratio,
            "durationSeconds": duration,
        }
    }

    # Submit request
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if resp.status_code != 200:
        print(f"Veo API error {resp.status_code}: {resp.text[:200]}")
        return None

    operation = resp.json()
    operation_name = operation.get("name", "")
    if not operation_name:
        print("No operation name returned")
        return None

    # Poll for completion (Veo takes 30-120 seconds)
    poll_url = f"{BASE_URL}/{operation_name}?key={GEMINI_API_KEY}"
    max_attempts = 30
    for attempt in range(max_attempts):
        time.sleep(10)
        poll_resp = requests.get(poll_url, timeout=30)
        if poll_resp.status_code != 200:
            continue

        result = poll_resp.json()
        if result.get("done"):
            # Extract video URI
            videos = result.get("response", {}).get("generatedVideos", [])
            if not videos:
                print("No videos in response")
                return None

            video_uri = videos[0].get("video", {}).get("uri", "")
            if not video_uri:
                print("No video URI")
                return None

            # Download the clip
            return _download_clip(video_uri, index)

        print(f"Clip {index+1}: still generating... ({attempt+1}/{max_attempts})")

    print(f"Clip {index+1}: timed out after {max_attempts * 10}s")
    return None


def _download_clip(uri: str, index: int) -> str:
    """Download video from URI and save to disk."""
    download_url = f"{uri}&key={GEMINI_API_KEY}"
    resp = requests.get(download_url, timeout=60)
    if resp.status_code != 200:
        print(f"Download failed: {resp.status_code}")
        return None

    path = f"{OUTPUT_DIR}/clip_{index:02d}.mp4"
    with open(path, "wb") as f:
        f.write(resp.content)
    return path


if __name__ == "__main__":
    # Quick test
    test_prompts = [
        "26-year-old Indian male dark navy t-shirt shocked expression looks at camera says 'Did you know iPhone 18 just changed everything?' dark studio blue rim light 9:16 vertical 8 seconds photorealistic",
        "Same 26-year-old Indian male dark navy t-shirt points at holographic display showing text 'Battery 40% bigger | Camera 2x faster' explains facts confidently 9:16 vertical 8 seconds photorealistic",
        "Same 26-year-old Indian male dark navy t-shirt turns to camera knowing smile says 'Now you know. Follow for more.' holographic text FOLLOW FOR MORE floats foreground 9:16 vertical 8 seconds photorealistic",
    ]
    paths = generate_clips(test_prompts)
    print(f"Generated {len(paths)} clips: {paths}")
