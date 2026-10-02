# agents_bhakti/bhakti_music_agent.py
"""Deity-aware music selection + dynamic music timeline (spec sections 16-17).

Reuses music_agent.get_background_music (Freesound, CC0 first, cached).
Adds: deity-specific query hints, variety across videos (recently used
tracks are skipped when an alternative exists), and a per-scene gain
envelope so music builds toward the divine moment and softens at the end.
"""

import json
import os

from agents_bhakti import music_agent

DEITY_HINTS = {
    "krishna": "krishna bhajan chant flute bansuri",
    "radha": "krishna bhajan chant flute bansuri",
    "shiv": "om namah shivaya damru ambient chant",
    "mahadev": "om namah shivaya damru ambient chant",
    "hanuman": "hanuman chalisa devotional percussion",
    "ram": "ram bhajan devotional flute orchestral",
    "durga": "durga devotional percussion chant",
    "devi": "durga devotional percussion chant",
    "ganesh": "ganesh aarti devotional bells",
    "vishnu": "vishnu chant ambient bells",
    "lakshmi": "aarti bells devotional",
    "saraswati": "veena tanpura calm",
}
RECENT_FILE = "output/bhakti_recent_music.json"
RECENT_KEEP = 6

# Music level (linear multiplier of the base music gain) per story purpose.
TIMELINE_GAIN = {"hook": 0.7, "setup": 1.0, "conflict": 1.15, "divine": 1.45,
                 "resolution": 1.0, "ending": 0.8}


def _recent():
    try:
        with open(RECENT_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _remember(name):
    os.makedirs("output", exist_ok=True)
    r = [n for n in _recent() if n != name] + [name]
    with open(RECENT_FILE, "w") as f:
        json.dump(r[-RECENT_KEEP:], f)


def select_devotional_music(research, scenes, title=""):
    """Returns the music record dict (path, license, name, author, url) or None."""
    deity = (research.get("deity") or "").lower()
    hint = next((h for k, h in DEITY_HINTS.items() if k in deity), "")
    topic_text = f"{research.get('topic', '')} {deity} {hint}".strip()

    recent = _recent()
    track = music_agent.get_background_music(topic_text, title)
    # Variety: if we got a track used very recently, try with another mood word once.
    if track and track["name"] in recent:
        alt = music_agent.get_background_music(f"{topic_text} meditation tanpura", title)
        if alt and alt["name"] not in recent:
            track = alt
    if track:
        _remember(track["name"])
    return track


def music_timeline(scenes, base_gain=1.0):
    """[(start, end, gain)] per scene for the mixer's volume automation."""
    return [(s.start, s.end, round(base_gain * TIMELINE_GAIN.get(s.purpose, 1.0), 3))
            for s in scenes]
