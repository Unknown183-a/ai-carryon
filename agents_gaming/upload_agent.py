# agents_gaming/upload_agent.py
"""
Same OAuth pattern as agents/upload_agent.py, but with its OWN token/secrets
env vars — this is a separate YouTube channel from English/Hindi/Cricket, so
it needs its own GitHub Secrets:
  YOUTUBE_GAMING_CLIENT_SECRETS_B64
  YOUTUBE_GAMING_TOKEN_B64
Generate the token the same way generate_english_token.py / generate_hindi_token.py
do (a generate_gaming_token.py following that same pattern is the natural
next file to add once you've created the Gaming channel's OAuth client).
"""
import os
import pickle
import base64
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def get_client_secrets_path():
    secrets_b64 = os.getenv("YOUTUBE_GAMING_CLIENT_SECRETS_B64")
    if secrets_b64:
        secrets_bytes = base64.b64decode(secrets_b64)
        temp_path = "/tmp/gaming_client_secrets.json"
        with open(temp_path, "wb") as f:
            f.write(secrets_bytes)
        return temp_path
    return "client_secrets_gaming.json"


def authenticate_youtube():
    creds = None

    token_b64 = os.getenv("YOUTUBE_GAMING_TOKEN_B64")
    if token_b64:
        creds = pickle.loads(base64.b64decode(token_b64))
    elif os.path.exists("token_gaming.pickle"):
        with open("token_gaming.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(get_client_secrets_path(), SCOPES)
            creds = flow.run_local_server(port=0)
            with open("token_gaming.pickle", "wb") as token:
                pickle.dump(creds, token)

    return build("youtube", "v3", credentials=creds)


def upload_thumbnail(youtube, video_id, thumbnail_path):
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
        ).execute()
    except Exception as e:
        print(f"Thumbnail upload failed: {e}")


def upload_video(video_path, title, description, hashtags, thumbnail_path=None, category_id="20"):
    """category_id 20 = Gaming (English/Hindi use 28 = Science & Tech)."""
    youtube = authenticate_youtube()

    if isinstance(hashtags, list):
        hashtag_str = " ".join(hashtags)
        tags = [h.strip().replace("#", "") for h in hashtags]
    else:
        hashtag_str = hashtags
        tags = [h.strip().replace("#", "") for h in hashtags.split()]

    full_description = f'''{description}

━━━━━━━━━━━━━━━━━━━━━━━━
🎮 Subscribe for daily gaming highlights!
👍 Like if that clip was insane!
💬 Drop your reaction below!
━━━━━━━━━━━━━━━━━━━━━━━━

{hashtag_str} #Shorts #YouTubeShorts #Gaming'''
    tags = tags + ["Shorts", "YouTubeShorts", "Gaming", "Twitch", "GamingClips"]

    body = {
        "snippet": {
            "title": title,
            "description": full_description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=1024 * 1024 * 5)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

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
