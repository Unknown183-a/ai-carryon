"""
agents_bhakti/music_agent.py

Fetches free, CC-licensed instrumental background music from Freesound.org,
matched to the video's topic/title by mood keyword, with a tiered fallback
so a niche query never comes back completely empty. Prefers CC0 (public
domain, no attribution needed); falls back to CC-BY (needs attribution,
which the caller should append to the video description) only if no CC0
track is found. Caches downloads locally by search tier.

Requires: FREESOUND_API_KEY (free at https://freesound.org/apiv2/apply/)

Returns a dict: {"path", "license", "name", "author", "url"} or None if
every tier fails — the caller MUST treat None as "no track available"
and should not upload a silent video in that case.
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

CC0 = 'Creative Commons 0'
CC_BY = 'Attribution'

MOOD_MAP = [
    (["aarti", "diya", "deep"], ["aarti chant vocal", "temple bells", "temple ambient", "bells devotional"]),
    (["mantra", "dhyan", "meditation", "shanti"], ["om chanting vocal", "sanskrit mantra chant", "meditation drone", "tanpura"]),
    (["katha", "bhagwat", "pravachan", "satsang"], ["kirtan vocal chant", "harmonium instrumental", "harmonium", "indian instrumental calm"]),
    (["krishna", "radha", "bansuri", "flute"], ["krishna bhajan chant", "flute instrumental indian", "bansuri", "indian flute calm"]),
    (["shiv", "mahadev", "rudra"], ["om namah shivaya chant", "tibetan bowl", "om chant", "meditation drone"]),
    (["hanuman", "ram", "durga", "devi"], ["kirtan vocal chant", "indian devotional instrumental", "temple instrumental", "indian classical calm"]),
]
# Vocal-chant queries tried before pure instrumental ones, so a genuine
# sung/chanted recording wins whenever Freesound actually has one.
DEFAULT_QUERIES = ["sanskrit chant vocal", "kirtan chant", "indian instrumental meditation", "calm instrumental ambient", "peaceful instrumental"]


def _pick_queries(topic: str, title: str) -> list:
    text = f"{topic} {title}".lower()
    for keywords, queries in MOOD_MAP:
        if any(kw in text for kw in keywords):
            return queries + DEFAULT_QUERIES
    return DEFAULT_QUERIES


def _cache_key(query: str, license_name: str) -> str:
    return hashlib.md5(f"{query}|{license_name}".encode("utf-8")).hexdigest()


def _load_cache_index() -> dict:
    if os.path.exists(CACHE_INDEX):
        with open(CACHE_INDEX, "r") as f:
            return json.load(f)
    return {}


def _save_cache_index(index: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_INDEX, "w") as f:
        json.dump(index, f)


def _search_one(query: str, license_name: str, min_duration: float):
    resp = requests.get(
        FREESOUND_SEARCH_URL,
        params={
            "query": query,
            "token": FREESOUND_API_KEY,
            "filter": f'license:"{license_name}" duration:[{min_duration} TO 400]',
            "fields": "id,name,previews,duration,license,username,url",
            "sort": "rating_desc",
            "page_size": 5,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


def _download(track: dict, key: str) -> str:
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
    return local_path


def get_background_music(topic: str, title: str, min_duration: float = 20.0):
    if not FREESOUND_API_KEY:
        print("[music_agent:bhakti] FREESOUND_API_KEY not set — cannot fetch music")
        return None

    queries = _pick_queries(topic, title)
    index = _load_cache_index()

    for license_name in (CC0, CC_BY):
        for query in queries:
            key = _cache_key(query, license_name)

            if key in index and os.path.exists(index[key]["path"]):
                cached = index[key]
                print(f"[music_agent:bhakti] Using cached track for '{query}' ({license_name})")
                return cached

            print(f"[music_agent:bhakti] Searching Freesound: '{query}' ({license_name})")
            try:
                results = _search_one(query, license_name, min_duration)
            except Exception as e:
                print(f"[music_agent:bhakti] Search failed for '{query}': {e}")
                continue

            if not results:
                continue

            track = results[0]
            try:
                local_path = _download(track, key)
            except Exception as e:
                print(f"[music_agent:bhakti] Download failed: {e}")
                continue

            if not local_path:
                continue

            record = {
                "path": local_path,
                "license": license_name,
                "name": track.get("name", "Unknown"),
                "author": track.get("username", "Unknown"),
                "url": track.get("url", ""),
            }
            index[key] = record
            _save_cache_index(index)
            print(f"[music_agent:bhakti] Found '{track.get('name')}' by {track.get('username')} ({license_name})")
            return record

    print("[music_agent:bhakti] Exhausted all queries and licenses — no track found")
    return None
