"""Standalone test: uploads a local video file to the cricket YouTube channel.
Doesn't touch the CricAPI/script pipeline — just validates OAuth + upload works."""
import sys
from agents_cricket.upload_agent import upload_video

if len(sys.argv) < 2:
    print("Usage: python test_upload.py <path_to_video.mp4>")
    sys.exit(1)

video_path = sys.argv[1]

video_id, video_url = upload_video(
    video_path=video_path,
    title="Test Upload - AI CarryON Cricket",
    description="Testing the automated upload pipeline. Ignore this video.",
    hashtags=["#Cricket", "#Test"],
)

print(f"\nSuccess! Video ID: {video_id}")
print(f"URL: {video_url}")
