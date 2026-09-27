# agents_bhakti/view_tracker_agent.py
"""
View tracking for the Bhakti channel — uses agents_bhakti.upload_agent's
readonly-scoped client and writes to SQLite with channel="bhakti".
"""

import datetime


def get_recent_videos_bhakti(max_videos=20):
    from agents_bhakti.upload_agent import get_youtube_client_readonly

    yt = get_youtube_client_readonly()

    channels_response = yt.channels().list(part="contentDetails", mine=True).execute()
    uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    playlist_response = yt.playlistItems().list(
        part="snippet",
        playlistId=uploads_playlist_id,
        maxResults=max_videos,
    ).execute()

    video_ids = [item["snippet"]["resourceId"]["videoId"] for item in playlist_response.get("items", [])]

    if not video_ids:
        return []

    stats_response = yt.videos().list(
        part="statistics,snippet",
        id=",".join(video_ids),
    ).execute()

    videos = []
    for item in stats_response.get("items", []):
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})
        videos.append({
            "id": item["id"],
            "title": snippet.get("title", ""),
            "published": snippet.get("publishedAt", ""),
            "url": f"https://youtube.com/watch?v={item['id']}",
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
        })

    return videos


def track_views_bhakti(max_videos=20):
    try:
        from agents.database import db
        use_db = True
    except Exception as e:
        print(f"Bhakti DB not available: {e}")
        use_db = False

    try:
        videos = get_recent_videos_bhakti(max_videos)
    except Exception as e:
        print(f"Bhakti view tracking error: {e}")
        return {}

    now = datetime.datetime.now(datetime.UTC).isoformat()
    history = {}

    for v in videos:
        vid = v["id"]

        if use_db:
            try:
                db.upsert_video(
                    video_id=vid,
                    title=v["title"],
                    published=v.get("published", ""),
                    channel="bhakti",
                )
                db.add_snapshot(
                    video_id=vid,
                    views=v["views"],
                    likes=v["likes"],
                    comments=v["comments"],
                    timestamp=now,
                )
            except Exception as e:
                print(f"Bhakti DB write error for {vid}: {e}")

        history[vid] = v

    if use_db:
        print(f"✅ Tracked {len(videos)} Bhakti videos")

    return history


if __name__ == "__main__":
    h = track_views_bhakti()
    print(f"Tracked {len(h)} Bhakti videos")
