# agents_bhakti/bhakti_sfx_agent.py
"""Scene-synced SFX (spec section 18). CC0 Freesound only (no attribution burden).
Missing SFX are skipped silently - they are optional garnish."""

import os
import re
import requests

from agents_bhakti.music_agent import FREESOUND_API_KEY, FREESOUND_SEARCH_URL, CC0

SFX_DIR = "output/sfx_cache"
SFX_QUERIES = {
    "temple_bell": "temple bell", "conch": "conch shell", "diya_fire": "small fire crackle",
    "wind": "soft wind", "rain": "light rain", "river": "river stream", "birds": "morning birds",
    "footsteps": "footsteps stone", "forest": "forest ambience", "crowd": "crowd murmur temple",
    "divine_chime": "chime magical", "thunder": "distant thunder",
}
# loudness in dB relative to the voice (spec: -18 .. -26 dB)
SFX_GAIN_DB = {"temple_bell": -22, "conch": -20, "divine_chime": -20, "thunder": -21}
DEFAULT_GAIN_DB = -24
MAX_SFX_SECONDS = 6.0


def _fetch(name):
    if not FREESOUND_API_KEY or name not in SFX_QUERIES:
        return None
    os.makedirs(SFX_DIR, exist_ok=True)
    local = os.path.join(SFX_DIR, f"{re.sub(r'[^a-z_]', '', name)}.mp3")
    if os.path.exists(local):
        return local
    try:
        r = requests.get(FREESOUND_SEARCH_URL, params={
            "query": SFX_QUERIES[name], "token": FREESOUND_API_KEY,
            "filter": f'license:"{CC0}" duration:[1 TO 12]',
            "fields": "id,name,previews,duration", "sort": "rating_desc", "page_size": 3}, timeout=15)
        r.raise_for_status()
        for t in r.json().get("results", []):
            url = t.get("previews", {}).get("preview-hq-mp3")
            if not url:
                continue
            a = requests.get(url, timeout=20)
            a.raise_for_status()
            with open(local, "wb") as f:
                f.write(a.content)
            return local
    except Exception as e:
        print(f"[bhakti_sfx] '{name}' unavailable: {e}")
    return None


def generate_sfx_plan(scenes, fetch=_fetch, max_total=8):
    """[{name, path, at, gain_db, max_dur}] - at = scene start (+0.15s)."""
    plan, last_by_name = [], {}
    for sc in scenes:
        for name in sc.sfx[:2]:
            # don't spam the same effect in back-to-back scenes
            if name in last_by_name and sc.scene_id - last_by_name[name] < 2:
                continue
            path = fetch(name)
            if not path:
                continue
            plan.append({"name": name, "path": path, "at": round(sc.start + 0.15, 2),
                         "gain_db": SFX_GAIN_DB.get(name, DEFAULT_GAIN_DB),
                         "max_dur": min(MAX_SFX_SECONDS, max(sc.duration, 1.5))})
            last_by_name[name] = sc.scene_id
            if len(plan) >= max_total:
                return plan
    return plan
