# agents/trending_agent.py
import os
import random
import googleapiclient.discovery
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Mass appeal categories — broad audience, high search volume
CATEGORY_IDS = [
    "28",  # Science & Technology — PRIMARY
    "25",  # News & Politics — for big tech news
    "26",  # Howto & Style — for tech tutorials
]

# High performing topic boosters — titles containing these get priority
POWER_KEYWORDS = [
    "iphone", "samsung", "apple", "google", "leaked", "secret",
    "revealed", "hack", "trick", "warning", "free", "banned",
    "vs", "beats", "record", "first", "new", "just released",
    "you didn't know", "nobody tells you", "stop doing",
]

# Topics to avoid — too niche, low search volume
AVOID_KEYWORDS = [
    "claude", "llm", "langchain", "hugging face", "fine-tuning",
    "embeddings", "vector database", "rag pipeline", "token",
    "benchmark", "parameter", "weights", "transformer architecture",
    "ring", "jewelry", "fashion", "cooking", "recipe", "makeup",
    "sport", "football", "cricket", "basketball", "race", "running",
    "music", "song", "album", "movie", "film", "drama", "series",
    "bypass", "plumbing", "gardening", "fitness", "workout", "diet",
]


def get_trending_topic(region_code="US"):
    youtube = googleapiclient.discovery.build(
        "youtube", "v3", developerKey=YOUTUBE_API_KEY
    )

    all_videos = []

    categories_to_try = random.sample(CATEGORY_IDS, min(3, len(CATEGORY_IDS)))

    for category_id in categories_to_try:
        try:
            request = youtube.videos().list(
                part="snippet,statistics",
                chart="mostPopular",
                regionCode=region_code,
                maxResults=50,
                videoCategoryId=category_id
            )
            response = request.execute()
            all_videos.extend(response.get("items", []))
        except Exception:
            continue

    if not all_videos:
        return _fallback_topic()

    scored = []
    for video in all_videos:
        snippet = video["snippet"]
        stats   = video.get("statistics", {})
        title   = snippet["title"]
        views   = int(stats.get("viewCount", 0))

        if not all(ord(c) < 128 for c in title):
            continue

        title_lower = title.lower()
        if any(kw in title_lower for kw in AVOID_KEYWORDS):
            continue

        score = views

        if any(kw in title_lower for kw in POWER_KEYWORDS):
            score *= 2

        try:
            published = datetime.fromisoformat(
                snippet["publishedAt"].replace("Z", "+00:00")
            )
            if published >= datetime.now(timezone.utc) - timedelta(hours=48):
                score *= 1.5
        except Exception:
            pass

        scored.append((score, title))

    if not scored:
        return _fallback_topic()

    scored.sort(reverse=True)

    # Final validation — must contain at least one tech signal
    TECH_SIGNALS = [
        "ai", "iphone", "samsung", "apple", "google", "microsoft", "tech",
        "robot", "chip", "cpu", "gpu", "phone", "laptop", "app", "software",
        "hack", "cyber", "data", "camera", "battery", "5g", "electric",
        "gadget", "device", "computer", "internet", "crypto", "space", "nasa",
        "tesla", "elon", "openai", "chatgpt", "gemini", "claude", "meta",
        "vr", "ar", "drone", "satellite", "quantum", "neural", "model",
    ]
    tech_pool = [
        title for _, title in scored[:20]
        if any(sig in title.lower() for sig in TECH_SIGNALS)
    ]

    if tech_pool:
        return random.choice(tech_pool[:10])

    return _fallback_topic()


def _fallback_topic():
    fallbacks = [
        "iPhone 17 Pro Max leaked features",
        "Samsung Galaxy secret feature you didn't know",
        "Apple just revealed something huge",
        "Google's new AI beats everything",
        "This phone trick nobody tells you",
        "Warning: stop doing this on your iPhone",
        "New gadget everyone is buying right now",
        "They don't want you to know this tech secret",
        "Apple vs Samsung who wins in 2026",
        "This free app replaces expensive software",
    ]
    return random.choice(fallbacks)
