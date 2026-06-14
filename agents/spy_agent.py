import os
# agents/spy_agent.py
from agents.analytics_agent import authenticate

TOP_CHANNELS = {
    'Fireship': 'UCsBjURrPoezykLs9EqgamOA',
    'MKBHD': 'UCBJycsmduvYEL83R_U4JriQ',
    'Two Minute Papers': 'UCbfYPyITQ-7l4upoX8nvctg',
    'Computerphile': 'UC9-y-6csu5WGm29I7JiwpnA',
    'AI Explained': 'UCNJ1Ymd5yFuUPtn21xtRbbw',
}

def get_trending_topics(max_per_channel=3):
    import json, time
    CACHE_FILE = "output/spy_cache.json"
    
    # Return cache if less than 6 hours old
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        if time.time() - cache["timestamp"] < 21600:
            print("Using cached trending topics")
            return cache["topics"]

    yt = authenticate()
    trending = []

    for channel_name, channel_id in TOP_CHANNELS.items():
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
                trending.append({
                    'channel': channel_name,
                    'title': item['snippet']['title'],
                    'views': int(item['statistics'].get('viewCount', 0)),
                    'likes': int(item['statistics'].get('likeCount', 0)),
                    'published': item['snippet']['publishedAt'][:10],
                    'url': f"https://youtube.com/watch?v={item['id']}",
                    'topic': item['snippet']['title'].split('#')[0].strip()
                })
        except Exception as e:
            print(f"Error fetching {channel_name}: {e}")
            continue

    result = sorted(trending, key=lambda x: x['views'], reverse=True)
    
    # Save to cache
    import json, time
    os.makedirs("output", exist_ok=True)
    with open("output/spy_cache.json", "w") as f:
        json.dump({"timestamp": time.time(), "topics": result}, f)
    
    if not result:
        # Fallback hardcoded top videos when API quota exceeded
        result = [
            {"channel": "Fireship", "title": "C in 100 Seconds", "views": 3783405, "likes": 119911, "published": "2021-03-17", "url": "https://youtube.com/watch?v=U3aXWizDbQ4", "topic": "C programming language explained"},
            {"channel": "Fireship", "title": "Rust in 100 Seconds", "views": 2432512, "likes": 83736, "published": "2021-05-11", "url": "https://youtube.com/watch?v=5C_HPTJg1lc", "topic": "Rust programming language explained"},
            {"channel": "Two Minute Papers", "title": "4 Experiments Where the AI Outsmarted Its Creators", "views": 1948562, "likes": 49953, "published": "2022-01-08", "url": "https://youtube.com/watch?v=78dFMgPlFCU", "topic": "AI outsmarting its creators experiments"},
            {"channel": "MKBHD", "title": "The World Largest iPhone Has a Secret", "views": 43411229, "likes": 1908741, "published": "2023-06-22", "url": "https://youtube.com/watch?v=FNnK1J-BdiM", "topic": "World largest iPhone secret revealed"},
            {"channel": "Fireship", "title": "Python in 100 Seconds", "views": 5200000, "likes": 150000, "published": "2021-02-10", "url": "https://youtube.com/watch?v=x7X9w_GIm1s", "topic": "Python programming language explained"},
            {"channel": "Computerphile", "title": "Quick Sort", "views": 431422, "likes": 11480, "published": "2013-08-22", "url": "https://youtube.com/watch?v=XE4VP_8Y0BU", "topic": "Quick sort algorithm explained"},
        ]
    return result
