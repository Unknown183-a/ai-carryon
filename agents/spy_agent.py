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
    
    return result
