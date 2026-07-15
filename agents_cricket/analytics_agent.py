# agents_cricket/analytics_agent.py
"""
Analytics for the Cricket channel — same interface as agents/analytics_agent.py
(get_channel_stats, get_recent_videos) but authenticated as the cricket
channel via agents_cricket.upload_agent's pickled credentials, since cricket
runs on a separate Google account/channel from English and Hindi.
"""


def get_channel_stats():
    from agents_cricket.upload_agent import get_youtube_client_readonly

    youtube = get_youtube_client_readonly()
    response = youtube.channels().list(part="statistics,snippet", mine=True).execute()
    channel = response["items"][0]
    return {
        "name": channel["snippet"]["title"],
        "subscribers": int(channel["statistics"].get("subscriberCount", 0)),
        "total_views": int(channel["statistics"].get("viewCount", 0)),
        "video_count": int(channel["statistics"].get("videoCount", 0)),
    }


def get_recent_videos(max_results=20):
    from agents_cricket.upload_agent import get_youtube_client_readonly

    youtube = get_youtube_client_readonly()

    channel = youtube.channels().list(part="contentDetails", mine=True).execute()
    uploads_playlist = channel["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    playlist_response = youtube.playlistItems().list(
        part="snippet",
        playlistId=uploads_playlist,
        maxResults=max_results,
    ).execute()

    video_ids = [item["snippet"]["resourceId"]["videoId"] for item in playlist_response.get("items", [])]
    if not video_ids:
        return []

    videos_response = youtube.videos().list(
        part="statistics,snippet",
        id=",".join(video_ids),
    ).execute()

    videos = []
    for item in videos_response["items"]:
        stats = item["statistics"]
        videos.append({
            "id": item["id"],
            "title": item["snippet"]["title"],
            "published": item["snippet"]["publishedAt"][:10],
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "url": f"https://youtube.com/watch?v={item['id']}",
        })

    return sorted(videos, key=lambda x: x["views"], reverse=True)
