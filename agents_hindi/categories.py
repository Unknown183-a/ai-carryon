# agents_hindi/categories.py
#
# Hindi channel V2 — Step 1: content focus.
# The channel only makes EXPERIMENT-style videos inside these four areas.
# Edit CATEGORIES to change the mix (weights are relative, not percentages).

import random
import re

CATEGORIES = {
    "science": {
        "label": "Science experiments",
        "weight": 4,
        "keywords": ("chemical", "chemistry", "physics", "reaction", "dry ice",
                     "magnet", "density", "pressure", "vacuum", "crystal",
                     "foam", "liquid", "acid", "surface tension", "vigyan"),
    },
    "ai": {
        "label": "AI experiments",
        "weight": 3,
        "keywords": ("ai ", " ai", "chatgpt", "gemini", "claude", "llm",
                     "midjourney", "sora", "veo", "deepfake", "voice clone",
                     "prompt", "artificial intelligence", "machine learning"),
    },
    "tech": {
        "label": "Tech experiments",
        "weight": 2,
        "keywords": ("wifi", "wi-fi", "bluetooth", "5g", "robot", "drone",
                     "3d print", "arduino", "raspberry", "circuit", "laser",
                     "software", "app ", "internet", "hacking", "code"),
    },
    "gadgets": {
        "label": "Gadget experiments",
        "weight": 2,
        "keywords": ("phone", "smartphone", "gadget", "earbuds", "headphone",
                     "smartwatch", "charger", "power bank", "camera", "laptop",
                     "iphone", "android", "battery", "drop test", "water test"),
    },
}

DEFAULT_CATEGORY = "science"


def category_names():
    return list(CATEGORIES.keys())


def pick_category(last_category=None):
    """Weighted random pick. Avoids repeating the last category when possible,
    so the channel does not get 5 AI videos in a row."""
    names = category_names()
    pool = [n for n in names if n != last_category] or names
    weights = [CATEGORIES[n]["weight"] for n in pool]
    return random.choices(pool, weights=weights, k=1)[0]


def classify_topic(text):
    """Best-effort category guess from a topic/title. Returns None if no
    keyword matches (caller decides the fallback)."""
    t = f" {(text or '').lower()} "
    best, best_hits = None, 0
    for name, cfg in CATEGORIES.items():
        hits = sum(1 for k in cfg["keywords"] if k in t)
        if hits > best_hits:
            best, best_hits = name, hits
    return best


def normalize_category(value, fallback_text=""):
    """Accept an LLM-supplied category; fix it if it is not one of ours."""
    v = (value or "").strip().lower()
    if v in CATEGORIES:
        return v
    return classify_topic(fallback_text) or DEFAULT_CATEGORY


# ─────────────────────────────────────────────
# Hindi language check (Devanagari OR Roman Hinglish)
# ─────────────────────────────────────────────

_HINGLISH_MARKERS = {
    "hai", "hain", "ka", "ki", "ke", "ko", "se", "mein", "nahi", "yeh", "ye",
    "aur", "par", "toh", "kya", "kaise", "jab", "hota", "hoti", "hota", "kar",
    "karo", "dekho", "yaar", "suno", "sach", "bhi", "ek", "tum",
}


def looks_hindi(text, min_marker_ratio=0.15, min_devanagari_ratio=0.3):
    """True if text is Hindi (Devanagari) or Hinglish (Roman). False for
    mostly-English text. The channel currently writes Roman Hinglish, so both
    forms must pass."""
    if not text:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    deva = sum(1 for c in letters if "\u0900" <= c <= "\u097F")
    if deva / len(letters) >= min_devanagari_ratio:
        return True
    words = re.findall(r"[a-z]+", text.lower())
    if not words:
        return False
    hits = sum(1 for w in words if w in _HINGLISH_MARKERS)
    return hits / len(words) >= min_marker_ratio
