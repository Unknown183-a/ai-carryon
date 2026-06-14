# agents/analytics_agent.py
import os
import pickle
import base64
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly"
]

ANALYTICS_TOKEN = "output/analytics_token.pickle"

def get_client_secrets_path():
    secrets_b64 = os.getenv("YOUTUBE_CLIENT_SECRETS_B64")
    if secrets_b64:
        secrets_bytes = base64.b64decode(secrets_b64)
        temp_path = "/tmp/client_secrets.json"
        with open(temp_path, "wb") as f:
            f.write(secrets_bytes)
        return temp_path
    return "client_secrets.json"

def authenticate():
    creds = None

    if os.path.exists(ANALYTICS_TOKEN):
        with open(ANALYTICS_TOKEN, "rb") as f:
            creds = pickle.load(f)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(ANALYTICS_TOKEN, "wb") as f:
            pickle.dump(creds, f)
        return build("youtube", "v3", credentials=creds)

    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file(
            get_client_secrets_path(), SCOPES
        )
        creds = flow.run_local_server(port=0)
        os.makedirs("output", exist_ok=True)
        with open(ANALYTICS_TOKEN, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)

def get_channel_stats():
    youtube = authenticate()
    response = youtube.channels().list(
        part="statistics,snippet",
        mine=True
    ).execute()
    channel = response["items"][0]
    return {
        "name": channel["snippet"]["title"],
        "subscribers": int(channel["statistics"].get("subscriberCount", 0)),
        "total_views": int(channel["statistics"].get("viewCount", 0)),
        "video_count": int(channel["statistics"].get("videoCount", 0)),
    }

def get_recent_videos(max_results=10):
    youtube = authenticate()

    channel = youtube.channels().list(
        part="contentDetails",
        mine=True
    ).execute()
    uploads_playlist = channel["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    playlist_response = youtube.playlistItems().list(
        part="snippet",
        playlistId=uploads_playlist,
        maxResults=max_results
    ).execute()

    video_ids = [item["snippet"]["resourceId"]["videoId"]
                 for item in playlist_response["items"]]

    if not video_ids:
        return []

    videos_response = youtube.videos().list(
        part="statistics,snippet",
        id=",".join(video_ids)
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
            "url": f"https://youtube.com/watch?v={item['id']}"
        })

    return sorted(videos, key=lambda x: x["views"], reverse=True)
