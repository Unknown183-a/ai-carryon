# agents_hindi/spy_agent.py
import os
import json
import time
from datetime import datetime, timedelta, timezone

HINDI_CHANNELS = {
    'Technical Guruji': 'UCkadhFcMFsvfZDSBVGcJiZg',
    'TechBurner': 'UCwfaAHy4zQUb2APNOGXUCCA',
    'Trakin Tech': 'UCnUSMmloOB6MKxfqygPJfoA',
    'Geeky Ranjit': 'UCHXeVVdHnfETFBB0WN1MHUw',
    'Technical Dost': 'UCu3GNxPgKrq8Gg3gYqGQwkw',
    'GadgetsToUse': 'UCbdp41UaYDKVlqhDqQ1UWEQ',
}

def get_hindi_trending_topics(max_per_channel=5):
    CACHE_FILE = "output/spy_cache_hindi.json"

    # Cache valid for 2 hours only
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        if time.time() - cache["timestamp"] < 7200:
            print("Using cached Hindi trending topics")
            return cache["topics"]

    try:
        from agents.analytics_agent import authenticate
        yt = authenticate()
        trending = []

        # Last 24 hours timestamp in RFC 3339 format
        since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        for channel_name, channel_id in HINDI_CHANNELS.items():
            try:
                # Search only videos published in last 24 hours
                results = yt.search().list(
                    part='snippet',
                    channelId=channel_id,
                    type='video',
                    videoDuration='short',
                    order='date',           # Most recent first
                    publishedAfter=since_24h,  # Last 24 hours only
                    maxResults=max_per_channel
                ).execute()

                video_ids = [item['id']['videoId'] for item in results['items']
                            if item['id'].get('videoId')]

                if not video_ids:
                    print(f"{channel_name}: No videos in last 24 hours")
                    continue

                stats = yt.videos().list(
                    part='statistics,snippet',
                    id=','.join(video_ids)
                ).execute()

                for item in stats['items']:
                    snippet = item['snippet']
                    published = snippet['publishedAt']

                    # Double-check published in last 24 hours
                    pub_time = datetime.fromisoformat(
                        published.replace("Z", "+00:00")
                    )
                    if pub_time < datetime.now(timezone.utc) - timedelta(hours=24):
                        continue

                    trending.append({
                        'channel': channel_name,
                        'title': snippet['title'],
                        'description': snippet.get('description', '')[:200],
                        'tags': snippet.get('tags', [])[:10],
                        'views': int(item['statistics'].get('viewCount', 0)),
                        'likes': int(item['statistics'].get('likeCount', 0)),
                        'published': published[:10],
                        'published_time': published,
                        'url': f"https://youtube.com/watch?v={item['id']}",
                        'topic': snippet['title'].split('#')[0].strip()
                    })

            except Exception as e:
                print(f"Error fetching {channel_name}: {e}")
                continue

        # Sort by views (most viral first)
        result = sorted(trending, key=lambda x: x['views'], reverse=True)
        print(f"Found {len(result)} Hindi videos from last 24 hours")

    except Exception as e:
        print(f"API error: {e}")
        result = []

    # Save cache
    os.makedirs("output", exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump({"timestamp": time.time(), "topics": result}, f)

    return result


def get_best_hindi_topic():
    """Get the single best trending Hindi topic for scheduler"""
    topics = get_hindi_trending_topics()
    if topics:
        # Return the most viewed video from last 24 hours
        best = topics[0]
        print(f"Best Hindi topic: {best['topic']} ({best['views']:,} views)")
        return best
    return None
