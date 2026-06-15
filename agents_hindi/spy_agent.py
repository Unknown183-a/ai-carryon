# agents_hindi/spy_agent.py
import os
import json
import time

# Top Hindi Tech YouTube Channels
HINDI_CHANNELS = {
    'Technical Guruji': 'UCkadhFcMFsvfZDSBVGcJiZg',
    'TechBurner': 'UCwfaAHy4zQUb2APNOGXUCCA',
    'Trakin Tech': 'UCnUSMmloOB6MKxfqygPJfoA',
    'Geeky Ranjit': 'UCHXeVVdHnfETFBB0WN1MHUw',
    'Technical Dost': 'UCu3GNxPgKrq8Gg3gYqGQwkw',
    'GadgetsToUse': 'UCbdp41UaYDKVlqhDqQ1UWEQ',
}

def get_hindi_trending_topics(max_per_channel=3):
    CACHE_FILE = "output/spy_cache_hindi.json"

    # Return cache if less than 6 hours old
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        if time.time() - cache["timestamp"] < 21600:
            print("Using cached Hindi trending topics")
            return cache["topics"]

    try:
        from agents.analytics_agent import authenticate
        yt = authenticate()
        trending = []

        for channel_name, channel_id in HINDI_CHANNELS.items():
            try:
                results = yt.search().list(
                    part='snippet',
                    channelId=channel_id,
                    type='video',
                    videoDuration='short',
                    order='viewCount',
                    maxResults=max_per_channel
                ).execute()

                video_ids = [item['id']['videoId'] for item in results['items']
                            if item['id'].get('videoId')]

                if not video_ids:
                    continue

                stats = yt.videos().list(
                    part='statistics,snippet',
                    id=','.join(video_ids)
                ).execute()

                for item in stats['items']:
                    snippet = item['snippet']
                    trending.append({
                        'channel': channel_name,
                        'title': snippet['title'],
                        'description': snippet.get('description', '')[:200],
                        'tags': snippet.get('tags', [])[:10],
                        'views': int(item['statistics'].get('viewCount', 0)),
                        'likes': int(item['statistics'].get('likeCount', 0)),
                        'published': snippet['publishedAt'][:10],
                        'url': f"https://youtube.com/watch?v={item['id']}",
                        'topic': snippet['title'].split('#')[0].strip()
                    })
            except Exception as e:
                print(f"Error fetching {channel_name}: {e}")
                continue

        result = sorted(trending, key=lambda x: x['views'], reverse=True)

    except Exception as e:
        print(f"API error: {e}")
        result = []

    # Fallback if API fails
    if not result:
        result = [
            {"channel": "Technical Guruji", "title": "iPhone 16 Pro Full Review Hindi", "views": 5200000, "likes": 180000, "published": "2024-09-20", "url": "https://youtube.com/watch?v=example1", "topic": "iPhone 16 Pro review", "description": "iPhone 16 Pro ka full review Hindi mein", "tags": ["iphone", "review", "hindi", "tech"]},
            {"channel": "TechBurner", "title": "5 Best Budget Phones 2024 Hindi", "views": 3800000, "likes": 120000, "published": "2024-10-01", "url": "https://youtube.com/watch?v=example2", "topic": "Best budget phones 2024", "description": "2024 ke best budget phones Hindi mein", "tags": ["budget", "phone", "hindi", "tech"]},
            {"channel": "Trakin Tech", "title": "AI Phone Features Jo Aap Nahi Jaante", "views": 2900000, "likes": 95000, "published": "2024-11-15", "url": "https://youtube.com/watch?v=example3", "topic": "AI phone features Hindi", "description": "AI phone features jo aap nahi jaante", "tags": ["ai", "phone", "features", "hindi"]},
            {"channel": "Geeky Ranjit", "title": "Sabse Sasta 5G Phone India Mein", "views": 4100000, "likes": 140000, "published": "2024-09-05", "url": "https://youtube.com/watch?v=example4", "topic": "Cheapest 5G phone India", "description": "India ka sabse sasta 5G phone", "tags": ["5g", "phone", "india", "hindi", "cheap"]},
            {"channel": "Technical Dost", "title": "ChatGPT Se Paise Kaise Kamaye", "views": 6200000, "likes": 210000, "published": "2024-08-20", "url": "https://youtube.com/watch?v=example5", "topic": "ChatGPT se paise kamao", "description": "ChatGPT se ghar baithe paise kaise kamaye", "tags": ["chatgpt", "ai", "paise", "hindi", "earn"]},
            {"channel": "GadgetsToUse", "title": "Free AI Tools Jo Aapki Life Badal De", "views": 3500000, "likes": 115000, "published": "2024-10-10", "url": "https://youtube.com/watch?v=example6", "topic": "Free AI tools Hindi", "description": "Free AI tools jo aapki life badal de", "tags": ["ai", "tools", "free", "hindi", "tech"]},
        ]

    # Save cache
    os.makedirs("output", exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump({"timestamp": time.time(), "topics": result}, f)

    return result
