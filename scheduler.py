# scheduler.py
import schedule
import time
import os
import datetime

from agents.research_agent import research
from agents.script_agent import create_script
from agents.seo_agent import generate_seo
from agents.thumbnail_agent import generate_thumbnail_text
from agents.thumbnail_generator import generate_thumbnail
from agents.image_agent import generate_backgrounds
from agents.voice_agent import generate_voice
from agents.caption_agent import create_srt
from agents.video_agent import create_video
from agents.upload_agent import upload_video
from agents.trending_agent import get_trending_topic

LOG_FILE = "output/scheduler_log.txt"
POSTED_TODAY_FILE = "output/posted_today.txt"


def log(message):
    os.makedirs("output", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def get_posted_today():
    """Returns list of (date, topic) posted today"""
    today = datetime.date.today().isoformat()
    posted = []

    if os.path.exists(POSTED_TODAY_FILE):
        with open(POSTED_TODAY_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith(today):
                    posted.append(line.split("|", 1)[1])

    return posted


def mark_posted_today(topic):
    today = datetime.date.today().isoformat()
    os.makedirs("output", exist_ok=True)
    with open(POSTED_TODAY_FILE, "a") as f:
        f.write(f"{today}|{topic}\n")


def get_fresh_trending_topic(max_attempts=5):
    """Get a trending topic not already posted today"""
    posted_today = get_posted_today()

    for attempt in range(max_attempts):
        topic = get_trending_topic(region_code="US")

        if topic not in posted_today:
            return topic

        log(f"Topic already posted today, retrying: {topic}")

    # Fallback: append a variation tag so it's still unique
    return topic + f" (Part {len(posted_today) + 1})"


def generate_and_upload():
    log("=== Starting scheduled video generation ===")

    try:
        log("Fetching trending YouTube topic...")
        topic = get_fresh_trending_topic()
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

        log("Generating thumbnail image...")
        thumbnail_image = generate_thumbnail(seo["title"], topic)

        log("Creating video...")
        video_file = create_video()

        log("Uploading to YouTube...")
        video_id, video_url = upload_video(
            video_path=video_file,
            title=seo["title"],
            description=seo["description"],
            hashtags=seo["hashtags"],
            thumbnail_path=thumbnail_image
        )

        mark_posted_today(topic)
        log(f"SUCCESS: Uploaded — {video_url}")

    except Exception as e:
        log(f"ERROR: {str(e)}")


# ─── Schedule Configuration ───────────────────────────────────────────────────
# Post 3 times per day at different times

schedule.every().day.at("09:00").do(generate_and_upload)
schedule.every().day.at("14:00").do(generate_and_upload)
schedule.every().day.at("19:00").do(generate_and_upload)

# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log("Scheduler started!")
    log(f"Next run: {schedule.next_run()}")

    generate_and_upload()  # TEST RUN - remove after testing

    while True:
        schedule.run_pending()
        time.sleep(60)