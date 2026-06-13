# scheduler.py
import schedule
import time
import os
import datetime

from agents.research_agent import research
from agents.script_agent import create_script
from agents.seo_agent import generate_seo
from agents.thumbnail_agent import generate_thumbnail_text
from agents.image_agent import generate_backgrounds
from agents.voice_agent import generate_voice
from agents.caption_agent import create_srt
from agents.video_agent import create_video
from agents.upload_agent import upload_video
from agents.trending_agent import get_trending_topic

LOG_FILE = "output/scheduler_log.txt"


def log(message):
    os.makedirs("output", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def generate_and_upload():
    log("=== Starting scheduled video generation ===")

    try:
        # Get trending topic automatically
        log("Fetching trending YouTube topic...")
        topic = get_trending_topic(region_code="US")
        log(f"Trending topic selected: {topic}")

        log("Researching...")
        research_data = research(topic)

        log("Writing script...")
        script = create_script(research_data)

        log("Generating SEO...")
        seo = generate_seo(topic, script)

        log("Generating thumbnail text...")
        generate_thumbnail_text(topic)

        log("Generating background images...")
        image_paths, image_errors = generate_backgrounds(topic, script, num_images=4)

        if not image_paths:
            log(f"ERROR: No images generated — {image_errors}")
            return

        log("Generating voiceover...")
        voice_file = generate_voice(script)

        log("Generating captions...")
        create_srt(script, voice_file)

        log("Creating video...")
        video_file = create_video()

        log("Uploading to YouTube...")
        video_id, video_url = upload_video(
            video_path=video_file,
            title=seo["title"],
            description=seo["description"],
            hashtags=seo["hashtags"]
        )

        log(f"SUCCESS: Uploaded — {video_url}")

    except Exception as e:
        log(f"ERROR: {str(e)}")


# ─── Schedule ─────────────────────────────────────────────────────────────────

schedule.every().day.at("09:00").do(generate_and_upload)

# Uncomment for testing every 30 mins:
# schedule.every(30).minutes.do(generate_and_upload)

# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log("Scheduler started!")
    log(f"Next run: {schedule.next_run()}")

    # Uncomment to test immediately:
    # generate_and_upload()

    while True:
        schedule.run_pending()
        time.sleep(60)