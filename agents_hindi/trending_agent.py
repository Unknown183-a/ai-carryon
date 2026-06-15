# agents_hindi/trending_agent.py
import os
import random
import googleapiclient.discovery
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def get_trending_topic(region_code="IN"):
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

    # Filter Hindi or Indian content from last 24 hours
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    pool = []

    for video in all_videos:
        snippet = video["snippet"]
        published = datetime.fromisoformat(
            snippet["publishedAt"].replace("Z", "+00:00")
        )
        lang = snippet.get("defaultAudioLanguage", "")
        title = snippet["title"]
        is_recent = published >= since

        # Accept Hindi, Indian English, or general English
        is_relevant = (
            lang.startswith("hi") or
            lang.startswith("en") or
            lang == "" 
        )

        if is_relevant:
            pool.append(title)

    if not pool:
        pool = [v["snippet"]["title"] for v in all_videos]

    if not pool:
        return "Artificial Intelligence kya hai"

    return random.choice(pool)
