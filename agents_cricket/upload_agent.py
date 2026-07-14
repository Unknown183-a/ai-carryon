# agents_cricket/upload_agent.py
import os
import pickle
import base64
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def authenticate_youtube():
    creds = None
    token_b64 = os.getenv("CRICKET_YOUTUBE_TOKEN_B64")
    if token_b64:
        creds = pickle.loads(base64.b64decode(token_b64))
    elif os.path.exists("cricket_token.pickle"):
        with open("cricket_token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds:
        raise RuntimeError(
            "No cricket YouTube token found. Generate one locally with the "
            "cricket channel's Google account, pickle it, base64-encode it, "
            "and set CRICKET_YOUTUBE_TOKEN_B64 on Render."
        )
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return build("youtube", "v3", credentials=creds)


def upload_video(video_path, title, description, hashtags, thumbnail_path=None):
    youtube = authenticate_youtube()

    hashtag_str = " ".join(hashtags) if isinstance(hashtags, list) else hashtags
    tags = [h.strip("#") for h in (hashtags if isinstance(hashtags, list) else hashtags.split())]

    full_description = f"""{description}

━━━━━━━━━━━━━━━━━━━━━━━━
🏏 Subscribe for daily cricket recaps!
━━━━━━━━━━━━━━━━━━━━━━━━

{hashtag_str} #Shorts #Cricket"""

    body = {
        "snippet": {
            "title": title,
            "description": full_description,
            "tags": tags + ["Shorts", "Cricket", "IPL"],
            "categoryId": "17",  # Sports
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=1024 * 1024 * 5)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumbnail_path)).execute()
        except Exception as e:
            print(f"Thumbnail upload failed: {e}")

    return video_id, f"https://www.youtube.com/watch?v={video_id}"
