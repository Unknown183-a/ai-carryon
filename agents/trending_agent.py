# agents/trending_agent.py
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

    # Last 24 hours timestamp
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    request = youtube.videos().list(
        part="snippet",
        chart="mostPopular",
        regionCode=region_code,
        maxResults=50,
        videoCategoryId="28"  # Science & Technology
    )
    response = request.execute()

    print(f"Fetching trending YouTube topics...")
    all_videos = response.get("items", [])
    print(f"Found {len(all_videos)} trending videos")

    # Filter to last 24 hours
    recent_videos = []
    for video in all_videos:
        published = video["snippet"]["publishedAt"]
        pub_time = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if pub_time >= datetime.fromisoformat(since):
            recent_videos.append(video)

    print(f"Published in last 24 hours: {len(recent_videos)} videos")

    # Use recent if available, otherwise fall back to all trending
    pool = recent_videos if recent_videos else all_videos

    if not pool:
        return "Artificial Intelligence explained"

    # Pick randomly
    video = random.choice(pool)
    title = video["snippet"]["title"]

    print(f"Selected topic: {title}")
    return title
