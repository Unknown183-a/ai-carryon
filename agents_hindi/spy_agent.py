# agents_hindi/spy_agent.py
import os
import json
import time
from datetime import datetime, timedelta, timezone

def get_hindi_trending_topics(max_results=20):
    CACHE_FILE = "output/spy_cache_hindi.json"

    # Cache valid for 2 hours
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        if time.time() - cache["timestamp"] < 7200:
            print("Using cached Hindi trending topics")
            return cache["topics"]

    try:
        from agents.analytics_agent import authenticate
        yt = authenticate()

        since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        trending = []

        # Search Hindi tech Shorts directly — no hardcoded channels
        search_queries = [
            "hindi tech shorts",
            "hindi technology facts",
            "hindi ai facts shorts",
            "tech facts hindi viral",
            "hindi gadgets shorts",
            "technology hindi shorts viral",
            "hindi science facts shorts",
        ]

        seen_ids = set()

        for query in search_queries:
            try:
                results = yt.search().list(
                    part='snippet',
                    q=query,
                    type='video',
                    videoDuration='short',
                    order='viewCount',
                    relevanceLanguage='hi',
                    regionCode='IN',
                    publishedAfter=since_24h,
                    maxResults=5
                ).execute()

                video_ids = [
                    item['id']['videoId']
                    for item in results['items']
                    if item['id'].get('videoId')
                    and item['id']['videoId'] not in seen_ids
                ]

                if not video_ids:
                    continue

                for vid in video_ids:
                    seen_ids.add(vid)

                stats = yt.videos().list(
                    part='statistics,snippet',
                    id=','.join(video_ids)
                ).execute()

                for item in stats['items']:
                    snippet = item['snippet']
                    published = snippet['publishedAt']

                    # Verify last 24 hours
                    pub_time = datetime.fromisoformat(
                        published.replace("Z", "+00:00")
                    )
                    if pub_time < datetime.now(timezone.utc) - timedelta(hours=24):
                        continue

                    # Filter: must have Hindi audio or Indian channel
                    lang = snippet.get('defaultAudioLanguage', '')
                    channel = snippet.get('channelTitle', '')
                    views = int(item['statistics'].get('viewCount', 0))

                    # Skip very low quality videos
                    if views < 1000:
                        continue

                    trending.append({
                        'channel': channel,
                        'title': snippet['title'],
                        'description': snippet.get('description', '')[:300],
                        'tags': snippet.get('tags', [])[:15],
                        'views': views,
                        'likes': int(item['statistics'].get('likeCount', 0)),
                        'published': published[:10],
                        'published_time': published,
                        'url': f"https://youtube.com/watch?v={item['id']}",
                        'topic': snippet['title'].split('#')[0].strip()
                    })

            except Exception as e:
                print(f"Query '{query}' error: {e}")
                continue

        # Sort by views
        result = sorted(trending, key=lambda x: x['views'], reverse=True)

        # Remove duplicates by topic
        seen_topics = set()
        unique_result = []
        for r in result:
            if r['topic'] not in seen_topics:
                seen_topics.add(r['topic'])
                unique_result.append(r)

        result = unique_result[:max_results]
        print(f"Found {len(result)} Hindi trending videos from last 24 hours")

    except Exception as e:
        print(f"API error: {e}")
        result = []

    # Fallback if nothing found in 24h — try last 7 days
    if not result:
        print("24h mein kuch nahi mila, 7 days try kar raha hai...")
        try:
            from agents.analytics_agent import authenticate
            yt = authenticate()
            since_7d = (datetime.now(timezone.utc) - timedelta(days=7)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            results = yt.search().list(
                part='snippet',
                q='hindi tech shorts viral',
                type='video',
                videoDuration='short',
                order='viewCount',
                relevanceLanguage='hi',
                regionCode='IN',
                publishedAfter=since_7d,
                maxResults=10
            ).execute()

            video_ids = [item['id']['videoId'] for item in results['items']
                        if item['id'].get('videoId')]

            if video_ids:
                stats = yt.videos().list(
                    part='statistics,snippet',
                    id=','.join(video_ids)
                ).execute()

                for item in stats['items']:
                    snippet = item['snippet']
                    result.append({
                        'channel': snippet.get('channelTitle', ''),
                        'title': snippet['title'],
                        'description': snippet.get('description', '')[:300],
                        'tags': snippet.get('tags', [])[:15],
                        'views': int(item['statistics'].get('viewCount', 0)),
                        'likes': int(item['statistics'].get('likeCount', 0)),
                        'published': snippet['publishedAt'][:10],
                        'published_time': snippet['publishedAt'],
                        'url': f"https://youtube.com/watch?v={item['id']}",
                        'topic': snippet['title'].split('#')[0].strip()
                    })

                result = sorted(result, key=lambda x: x['views'], reverse=True)[:max_results]
                print(f"7-day fallback: {len(result)} videos mili")

        except Exception as e:
            print(f"7-day fallback error: {e}")

    # Save cache
    os.makedirs("output", exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump({"timestamp": time.time(), "topics": result}, f)

    return result


def get_best_hindi_topic():
    """Get single best trending Hindi topic for scheduler"""
    topics = get_hindi_trending_topics()
    if topics:
        best = topics[0]
        print(f"Best Hindi topic: {best['topic']} ({best['views']:,} views)")
        return best
    return None
