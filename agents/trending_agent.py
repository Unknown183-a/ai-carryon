# agents/trending_agent.py
import os
import random
import googleapiclient.discovery
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def get_trending_topic(region_code="US"):
    youtube = googleapiclient.discovery.build(
        "youtube", "v3", developerKey=YOUTUBE_API_KEY
    )

    request = youtube.videos().list(
        part="snippet",
        chart="mostPopular",
        regionCode=region_code,
        maxResults=50,
        videoCategoryId="28"  # Science & Technology
    )
    response = request.execute()

    all_videos = response.get("items", [])

    # Filter English only + last 24 hours
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    pool = []
    for video in all_videos:
        snippet = video["snippet"]
        published = datetime.fromisoformat(
            snippet["publishedAt"].replace("Z", "+00:00")
        )
        lang = snippet.get("defaultAudioLanguage", "")
        title = snippet["title"]

        # Only English titles, recent videos
        is_english = lang.startswith("en") or (
            all(ord(c) < 128 for c in title)
        )
        is_recent = published >= since

        if is_english:
            pool.append(title)

    # Fallback to all English videos if no recent ones
    if not pool:
        pool = [
            v["snippet"]["title"] for v in all_videos
            if all(ord(c) < 128 for c in v["snippet"]["title"])
        ]

    if not pool:
        return "Artificial Intelligence future explained"

    return random.choice(pool)
