# agents/upload_agent.py
import os
import pickle
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def authenticate_youtube():
    creds = None

    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secrets.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    youtube = build("youtube", "v3", credentials=creds)
    return youtube


def upload_thumbnail(youtube, video_id, thumbnail_path):
    """Upload custom thumbnail to YouTube video"""
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

    tags = [tag.strip().replace("#", "") for tag in hashtags.split()]

    # Add #Shorts to description for YouTube algorithm
    full_description = description + "\n\n" + hashtags + "\n\n#Shorts"

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

    # Upload thumbnail if provided
    if thumbnail_path and os.path.exists(thumbnail_path):
        upload_thumbnail(youtube, video_id, thumbnail_path)

    return video_id, video_url