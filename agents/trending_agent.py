# agents/trending_agent.py
import os
import random
import googleapiclient.discovery
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# ONLY Science & Technology category
CATEGORY_IDS = ["28"]

# Must contain at least one of these to qualify
TECH_MUST_HAVE = [
    "ai", "artificial intelligence", "robot", "iphone", "samsung", "apple",
    "google", "microsoft", "tech", "chip", "cpu", "gpu", "phone", "laptop",
    "app", "software", "hack", "cyber", "data", "camera", "battery", "5g",
    "electric", "gadget", "device", "computer", "internet", "crypto",
    "space", "nasa", "tesla", "elon", "openai", "chatgpt", "gemini",
    "meta", "vr", "ar", "drone", "satellite", "quantum", "neural", "model",
    "invention", "technology", "innovation", "future", "new feature",
    "launched", "released", "revealed", "upgrade", "update", "version",
    "humanoid", "autonomous", "self-driving", "electric vehicle", "ev",
    "gpt", "llm", "machine learning", "deep learning", "automation",
]

# Immediately reject if contains any of these
TECH_BLOCKLIST = [
    "gift", "wedding", "love", "relationship", "dating", "family",
    "cooking", "recipe", "food", "fashion", "makeup", "beauty",
    "sport", "football", "cricket", "basketball", "soccer", "tennis",
    "music", "song", "album", "concert", "dance", "movie", "film",
    "drama", "series", "netflix", "disney", "celebrity", "actor",
    "politics", "election", "trump", "biden", "government", "war",
    "iran", "russia", "ukraine", "military", "president", "senator",
    "religion", "god", "prayer", "church", "mosque", "temple",
    "fitness", "workout", "diet", "weight loss", "gym", "yoga",
    "travel", "hotel", "vacation", "tourism", "beach", "holiday",
    "real estate", "house", "home decor", "interior", "garden",
    "animals", "pet", "dog", "cat", "wildlife", "nature",
    "funny", "prank", "challenge", "reaction", "vlog", "storytime",
    "she", "he", "her", "him", "waited", "gave", "surprised",
]


def is_tech_topic(title: str) -> bool:
    title_lower = title.lower()
    # Reject if blocklist word found
    if any(kw in title_lower for kw in TECH_BLOCKLIST):
        return False
    # Accept if tech signal found
    if any(kw in title_lower for kw in TECH_MUST_HAVE):
        return True
    return False


def get_trending_topic(region_code="US"):
    try:
        youtube = googleapiclient.discovery.build(
            "youtube", "v3", developerKey=YOUTUBE_API_KEY
        )

        all_videos = []

        # Fetch from Science & Technology only
        request = youtube.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode=region_code,
            maxResults=50,
            videoCategoryId="28"
        )
        response = request.execute()
        all_videos.extend(response.get("items", []))

        # Score and filter
        scored = []
        for video in all_videos:
            snippet = video["snippet"]
            stats = video.get("statistics", {})
            title = snippet["title"]
            views = int(stats.get("viewCount", 0))

            # English only
            if not all(ord(c) < 128 for c in title):
                continue

            # Must pass tech filter
            if not is_tech_topic(title):
                continue

            score = views

            # Boost recent videos
            try:
                published = datetime.fromisoformat(
                    snippet["publishedAt"].replace("Z", "+00:00")
                )
                if published >= datetime.now(timezone.utc) - timedelta(hours=48):
                    score *= 1.5
            except Exception:
                pass

            scored.append((score, title))

        if scored:
            scored.sort(reverse=True)
            top_pool = [title for _, title in scored[:10]]
            return random.choice(top_pool)

    except Exception as e:
        print(f"Trending agent error: {e}")

    return _fallback_topic()


def _fallback_topic():
    """Proven high-performing tech topics."""
    fallbacks = [
        "New AI robot that can do everything humans can",
        "Apple just revealed iPhone 17 Pro hidden features",
        "Google's new AI beats every model in the world",
        "This new invention will change how we use phones forever",
        "Tesla's new self-driving update just changed everything",
        "New humanoid robot just launched and it's insane",
        "OpenAI just released something nobody expected",
        "Samsung Galaxy S26 leaked features are mind blowing",
        "This AI tool replaces 10 apps for free",
        "New chip technology makes phones 10x faster",
        "NASA just discovered something that changes space forever",
        "The AI that can clone your voice in 3 seconds",
        "New electric vehicle beats Tesla at half the price",
        "This free AI tool is replacing expensive software",
        "Google just launched the most powerful AI assistant ever",
    ]
    return random.choice(fallbacks)
