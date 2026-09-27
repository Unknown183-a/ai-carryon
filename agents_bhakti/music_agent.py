"""
agents_bhakti/music_agent.py

Fetches free, CC0-licensed devotional/instrumental background music from
Freesound.org, matched to the video's topic/title by mood keyword, caches
it locally, and returns a path ready for ffmpeg mixing.

Requires: FREESOUND_API_KEY (free at https://freesound.org/apiv2/apply/)
"""

import os
import re
import json
import hashlib
import requests

FREESOUND_API_KEY = os.environ.get("FREESOUND_API_KEY")
FREESOUND_SEARCH_URL = "https://freesound.org/apiv2/search/text/"
CACHE_DIR = "output/music_cache"
CACHE_INDEX = os.path.join(CACHE_DIR, "cache_index.json")

# Map devotional keywords found in the topic/title to a search query that
# tends to return the right *mood* of instrumental track on Freesound.
MOOD_MAP = [
    (["aarti", "diya", "deep"], "temple bells ambient devotional"),
    (["mantra", "dhyan", "meditation", "shanti"], "meditation drone tanpura"),
    (["katha", "bhagwat", "pravachan", "satsang"], "soft harmonium instrumental"),
    (["krishna", "radha", "bansuri", "flute"], "bansuri flute instrumental indian"),
    (["shiv", "mahadev", "rudra"], "tibetan bowl om chant instrumental"),
    (["hanuman", "ram", "durga", "devi"], "indian devotional instrumental temple"),
]
DEFAULT_QUERY = "indian devotional instrumental meditation"


def _pick_query(topic: str, title: str) -> str:
    text = f"{topic} {title}".lower()
    for keywords, query in MOOD_MAP:
        if any(kw in text for kw in keywords):
            return query
    return DEFAULT_QUERY


def _cache_key(query: str) -> str:
    return hashlib.md5(query.encode("utf-8")).hexdigest()


def _load_cache_index() -> dict:
    if os.path.exists(CACHE_INDEX):
        with open(CACHE_INDEX, "r") as f:
            return json.load(f)
    return {}


def _save_cache_index(index: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_INDEX, "w") as f:
        json.dump(index, f)


def get_background_music(topic: str, title: str, min_duration: float = 20.0):
    """
    Returns a local file path to a CC0 instrumental track matched to the
    topic/title mood, or None if unavailable (caller should skip music
    gracefully rather than fail the pipeline).
    """
    if not FREESOUND_API_KEY:
        print("[music_agent:bhakti] FREESOUND_API_KEY not set — skipping background music")
        return None

    query = _pick_query(topic, title)
    key = _cache_key(query)
    index = _load_cache_index()

    # Serve from cache if we already downloaded this mood
    if key in index and os.path.exists(index[key]):
        print(f"[music_agent:bhakti] Using cached track for mood '{query}'")
        return index[key]

    print(f"[music_agent:bhakti] Searching Freesound for: {query}")
    try:
        resp = requests.get(
            FREESOUND_SEARCH_URL,
            params={
                "query": query,
                "token": FREESOUND_API_KEY,
                "filter": f'license:"Creative Commons 0" duration:[{min_duration} TO 400]',
                "fields": "id,name,previews,duration,license",
                "sort": "rating_desc",
                "page_size": 5,
            },
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception as e:
        print(f"[music_agent:bhakti] Freesound search failed: {e}")
        return None

    if not results:
        print(f"[music_agent:bhakti] No CC0 results for '{query}' — trying default query")
        if query != DEFAULT_QUERY:
            return get_background_music_by_query(DEFAULT_QUERY, min_duration)
        return None

    track = results[0]
    preview_url = track.get("previews", {}).get("preview-hq-mp3")
    if not preview_url:
        print("[music_agent:bhakti] Selected track has no downloadable preview — skipping")
        return None

    os.makedirs(CACHE_DIR, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", track["name"])[:40]
    local_path = os.path.join(CACHE_DIR, f"{key}_{safe_name}.mp3")

    try:
        audio_resp = requests.get(preview_url, timeout=20)
        audio_resp.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(audio_resp.content)
    except Exception as e:
        print(f"[music_agent:bhakti] Download failed: {e}")
        return None

    index[key] = local_path
    _save_cache_index(index)
    print(f"[music_agent:bhakti] Downloaded '{track['name']}' (CC0) -> {local_path}")
    return local_path


def get_background_music_by_query(query: str, min_duration: float):
    """Fallback helper used when the mood-specific search returns nothing."""
    key = _cache_key(query)
    index = _load_cache_index()
    if key in index and os.path.exists(index[key]):
        return index[key]
    try:
        resp = requests.get(
            FREESOUND_SEARCH_URL,
            params={
                "query": query,
                "token": FREESOUND_API_KEY,
                "filter": f'license:"Creative Commons 0" duration:[{min_duration} TO 400]',
                "fields": "id,name,previews,duration,license",
                "sort": "rating_desc",
                "page_size": 5,
            },
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None
        track = results[0]
        preview_url = track.get("previews", {}).get("preview-hq-mp3")
        if not preview_url:
            return None
        os.makedirs(CACHE_DIR, exist_ok=True)
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", track["name"])[:40]
        local_path = os.path.join(CACHE_DIR, f"{key}_{safe_name}.mp3")
        audio_resp = requests.get(preview_url, timeout=20)
        audio_resp.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(audio_resp.content)
        index[key] = local_path
        _save_cache_index(index)
        return local_path
    except Exception as e:
        print(f"[music_agent:bhakti] Fallback search failed: {e}")
        return None
