# agents/upload_agent.py
import os
import pickle
import base64
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_client_secrets_path():
    secrets_b64 = os.getenv("YOUTUBE_CLIENT_SECRETS_B64")
    if secrets_b64:
        secrets_bytes = base64.b64decode(secrets_b64)
        temp_path = "/tmp/client_secrets.json"
        with open(temp_path, "wb") as f:
            f.write(secrets_bytes)
        return temp_path
    return "client_secrets.json"


def authenticate_youtube():
    creds = None

    # Try loading from environment variable first (cloud deployment)
    token_b64 = os.getenv("YOUTUBE_TOKEN_B64")
    if token_b64:
        token_bytes = base64.b64decode(token_b64)
        creds = pickle.loads(token_bytes)

    # Fallback to local file
    elif os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            secrets_path = get_client_secrets_path()
            flow = InstalledAppFlow.from_client_secrets_file(
                secrets_path, SCOPES
            )
            creds = flow.run_local_server(port=0)
            with open("token.pickle", "wb") as token:
                pickle.dump(creds, token)

    youtube = build("youtube", "v3", credentials=creds)
    return youtube


def upload_thumbnail(youtube, video_id, thumbnail_path):
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
        ).execute()
        print(f"Thumbnail uploaded for video {video_id}")
    except Exception as e:
        print(f"Thumbnail upload failed: {e}")


def upload_video(video_path, title, description, hashtags,
                 thumbnail_path=None, category_id="28"):
    youtube = authenticate_youtube()

    # Handle both list and string hashtags
    if isinstance(hashtags, list):
        hashtag_str = " ".join(hashtags)
        tags = [h.strip().replace("#", "") for h in hashtags]
    else:
        hashtag_str = hashtags
        tags = [h.strip().replace("#", "") for h in hashtags.split()]

    full_description = f'''{description}

━━━━━━━━━━━━━━━━━━━━━━━━
🔔 Subscribe for daily AI & Tech Shorts!
👍 Like if you learned something new!
💬 Comment your thoughts below!
━━━━━━━━━━━━━━━━━━━━━━━━

{hashtag_str} #Shorts #YouTubeShorts'''
    tags = tags + ["Shorts", "YouTubeShorts", "AI", "Tech", "Technology"]

    body = {
        "snippet": {
            "title": title,
            "description": full_description,
            "tags": tags + ["Shorts"],
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 5
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    if thumbnail_path and os.path.exists(thumbnail_path):
        upload_thumbnail(youtube, video_id, thumbnail_path)

    return video_id, video_url
