"""
agents_hindi/view_tracker_agent.py — View tracking for Hindi channel

Uses agents_hindi.upload_agent's auth (Hindi channel credentials)
to fetch and track Hindi channel videos. Writes to SQLite with
channel="hindi" tag.
"""

import os
import datetime


def get_recent_videos_hindi(max_videos=20):
    """Fetch recent Hindi channel video stats."""
    from agents_hindi.upload_agent import get_youtube_client

    yt = get_youtube_client()

    # Get uploads playlist
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


def track_views_hindi(max_videos=20):
    """Track Hindi channel views — writes to SQLite with channel='hindi'."""
    try:
        from agents.database import db
        use_db = True
    except Exception as e:
        print(f"Hindi DB not available: {e}")
        use_db = False

    try:
        videos = get_recent_videos_hindi(max_videos)
    except Exception as e:
        print(f"Hindi view tracking error: {e}")
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
                    channel="hindi",
                )
                db.add_snapshot(
                    video_id=vid,
                    views=v["views"],
                    likes=v["likes"],
                    comments=v["comments"],
                    timestamp=now,
                )
            except Exception as e:
                print(f"Hindi DB write error for {vid}: {e}")

        history[vid] = v

    if use_db:
        print(f"✅ Tracked {len(videos)} Hindi videos")

    return history


if __name__ == "__main__":
    h = track_views_hindi()
    print(f"Tracked {len(h)} Hindi videos")
