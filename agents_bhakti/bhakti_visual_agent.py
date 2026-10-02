# agents_bhakti/bhakti_visual_agent.py
"""Pexels visual search + ranking + dedup (spec sections 7-9, 11, 12).

Per scene: run 3-5 queries, collect candidates (metadata only), filter,
rank, pick the best unused clip, then download only the winner.
"""

import json
import os
import re
import requests

PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
CLIP_DIR = "assets/pexels_clips"
USED_META_KEY = "bhakti_used_pexels_ids"
USED_LOCAL_FILE = "output/bhakti_used_pexels_ids.json"
USED_HISTORY = 300

# URL slugs / tags that signal unrelated or risky footage for a devotional video
BAD_WORDS = ["party", "bikini", "nightclub", "wedding dance", "fashion", "model", "sexy",
             "drunk", "casino", "gun", "war", "blood", "halloween", "christmas", "church",
             "mosque", "cross", "buddha statue"]
GOOD_WORDS = ["temple", "hindu", "indian", "india", "diya", "aarti", "prayer", "pray", "puja",
              "ganges", "ghat", "incense", "marigold", "sunrise", "sunset", "bell", "lamp",
              "candle", "flame", "river", "light", "rays", "mist", "storm", "clouds"]


def _used_ids():
    try:
        from agents.database import db
        raw = db.get_meta(USED_META_KEY)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    try:
        with open(USED_LOCAL_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _save_used_ids(ids):
    ids = ids[-USED_HISTORY:]
    try:
        from agents.database import db
        db.set_meta(USED_META_KEY, json.dumps(ids))
        return
    except Exception:
        pass
    os.makedirs("output", exist_ok=True)
    with open(USED_LOCAL_FILE, "w") as f:
        json.dump(ids, f)


def pick_file(video_files, target_w=1080):
    """Best mp4 encode: portrait preferred, closest to 1080 wide, never below 720."""
    mp4 = [f for f in video_files if f.get("file_type") == "video/mp4" and f.get("link")] or \
          [f for f in video_files if f.get("link")]
    if not mp4:
        return None
    ok = [f for f in mp4 if (f.get("width") or 0) >= 720] or mp4
    ok.sort(key=lambda f: abs((f.get("width") or 0) - target_w))
    return ok[0]


def score_candidate(video, query, query_rank, scene_duration, used_ids, session_ids):
    """Higher is better; returns None to reject. Pure function (unit-testable)."""
    vid = str(video.get("id"))
    if vid in session_ids:
        return None                       # never repeat inside one video
    f = pick_file(video.get("video_files", []))
    if not f:
        return None
    w, h = f.get("width") or 0, f.get("height") or 0
    dur = video.get("duration") or 0
    slug = (video.get("url") or "").lower().replace("-", " ")

    if any(b in slug for b in BAD_WORDS):
        return None
    if w and h and h < w:                  # landscape encode: reject, we want vertical
        return None
    if max(w, h) < 1280:                   # too low-res for 1080x1920
        return None
    if dur < min(3, scene_duration):
        return None

    score = 0.0
    score += 25 if h >= 1920 else 15       # resolution
    score += 15 if w and h and abs(w / h - 9 / 16) < 0.02 else 8   # true 9:16
    score += max(0, 20 - abs(dur - scene_duration * 1.3) * 1.5)    # duration fit (some room to trim)
    score += max(0, 20 - query_rank * 6)   # earlier queries are closer to the scene intent
    q_words = set(re.findall(r"[a-z]+", query.lower()))
    score += 4 * len(q_words & set(re.findall(r"[a-z]+", slug)))  # relevance by slug overlap
    score += 1.5 * sum(1 for g in GOOD_WORDS if g in slug)
    if vid in used_ids:
        score -= 35                        # recently used in earlier videos: strongly avoid
    return score


def search_candidates(query, per_page=15):
    key = os.getenv("PEXELS_API_KEY", "")
    if not key:
        raise RuntimeError("PEXELS_API_KEY not set")
    r = requests.get(
        PEXELS_VIDEO_URL, headers={"Authorization": key},
        params={"query": query, "orientation": "portrait", "size": "medium", "per_page": per_page},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("videos", [])


def select_clip_for_scene(scene, used_ids, session_ids, search=None, exclude=()):
    """Returns (video_dict, query) for the best candidate, or (None, None)."""
    search = search or search_candidates
    dur = max(scene.duration, 3.0) if scene.duration else 5.0
    best, best_score, best_q = None, None, None
    seen = set()
    for rank, q in enumerate(scene.pexels_queries):
        try:
            videos = search(q)
        except Exception as e:
            print(f"[bhakti_visual] scene {scene.scene_id} query '{q}' failed: {e}")
            continue
        for v in videos:
            vid = str(v.get("id"))
            if vid in seen or vid in exclude:
                continue
            seen.add(vid)
            s = score_candidate(v, q, rank, dur, used_ids, session_ids)
            if s is not None and (best_score is None or s > best_score):
                best, best_score, best_q = v, s, q
        if best_score is not None and best_score >= 85:  # good enough, save API calls
            break
    return best, best_q


def download_clip(video, path):
    f = pick_file(video.get("video_files", []))
    resp = requests.get(f["link"], timeout=90, stream=True)
    resp.raise_for_status()
    with open(path, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            fh.write(chunk)
    return path


def fetch_scene_clips(scenes, exclude_by_scene=None, only=None, search=None, downloader=None):
    """Fill scene.clip_path / clip_id. `only` = set of scene_ids to (re)fetch."""
    search = search or search_candidates
    downloader = downloader or download_clip
    os.makedirs(CLIP_DIR, exist_ok=True)
    used = _used_ids()
    session = {s.clip_id for s in scenes if s.clip_id and (only is None or s.scene_id not in only)}
    exclude_by_scene = exclude_by_scene or {}
    failures = []
    for sc in scenes:
        if only is not None and sc.scene_id not in only:
            continue
        video, q = select_clip_for_scene(sc, set(used), session, search,
                                         exclude=exclude_by_scene.get(sc.scene_id, ()))
        if not video:
            failures.append(sc.scene_id)
            print(f"[bhakti_visual] scene {sc.scene_id}: no suitable clip")
            continue
        path = os.path.join(CLIP_DIR, f"scene_{sc.scene_id}_{video['id']}.mp4")
        try:
            downloader(video, path)
        except Exception as e:
            failures.append(sc.scene_id)
            print(f"[bhakti_visual] scene {sc.scene_id} download failed: {e}")
            continue
        sc.clip_path, sc.clip_id = path, str(video["id"])
        session.add(sc.clip_id)
        print(f"[bhakti_visual] scene {sc.scene_id} ({sc.purpose}) <- {video['id']} via '{q}'")
    # Persist usage only for clips that were kept
    _save_used_ids(used + [s.clip_id for s in scenes if s.clip_id and s.clip_id not in used])
    return failures
