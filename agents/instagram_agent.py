# agents/instagram_agent.py
import os
from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

def post_reel(video_path, caption):
    cl = Client()
    cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
    
    media = cl.clip_upload(
        video_path,
        caption=caption
    )
    
    print(f"Posted to Instagram! Media ID: {media.id}")
    return media.id
