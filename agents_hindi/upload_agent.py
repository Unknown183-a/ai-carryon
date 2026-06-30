# agents_hindi/upload_agent.py
import os
import json
import google.oauth2.credentials
import googleapiclient.discovery
import googleapiclient.http

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Broader scopes needed for view tracking (read channel stats, playlists, videos)
SCOPES_READ = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

def get_youtube_client():
    """Upload-only client — works with existing YOUTUBE_TOKEN_JSON."""
    return _build_client(SCOPES)


def get_youtube_client_readonly():
    """
    Read-capable client for view tracking (channels, playlists, videos.list).
    Requires a token with youtube.readonly scope — if the existing token
    doesn't have it, this will fail with insufficient_scope and view
    tracking should be skipped gracefully by the caller.
    """
    return _build_client(SCOPES_READ)


def _build_client(scopes):
    token_json = os.getenv("HINDI_TOKEN_JSON") or os.getenv("YOUTUBE_TOKEN_JSON")
    if not token_json:
        if os.path.exists("token_hindi.json"):
            token_json = open("token_hindi.json").read()
        else:
            raise ValueError("No Hindi YouTube token found")

    token_data = json.loads(token_json)
    credentials = google.oauth2.credentials.Credentials(
        token=token_data["token"],
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data.get("scopes", scopes)
    )
    return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

def upload_video(video_path, title, description, hashtags, thumbnail_path=None):
    youtube = get_youtube_client()
    
    tags = hashtags if isinstance(hashtags, list) else hashtags.split(",")
    
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:30],
            "categoryId": "28",
            "defaultLanguage": "hi",
            "defaultAudioLanguage": "hi"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }
    
    media = googleapiclient.http.MediaFileUpload(
        video_path, mimetype="video/mp4", resumable=True
    )
    
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    
    response = None
    while response is None:
        for retry in range(3):
                try:
                    status, response = request.next_chunk()
                    break
                except Exception as chunk_err:
                    if retry == 2:
                        raise
                    print(f"Chunk upload retry {retry+1}: {chunk_err}")
                    import time; time.sleep(5)
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")
    
    video_id = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=googleapiclient.http.MediaFileUpload(thumbnail_path)
            ).execute()
        except Exception as e:
            print(f"Thumbnail upload failed: {e}")
    
    print(f"Uploaded! {video_url}")
    return video_id, video_url
