import schedule
import time
import os
import datetime

os.environ['TZ'] = 'Asia/Kolkata'

LOG_FILE = "output/scheduler_log.txt"


def log(message):
    os.makedirs("output", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}"
    print(entry, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def generate_and_upload():
    log("=== Starting scheduled video generation ===")
    try:
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

        log("Fetching trending YouTube topic...")
        topic = get_trending_topic(region_code="US")
        log(f"Trending topic: {topic}")

        log("Researching...")
        research_data = research(topic)

        log("Writing script...")
        script = create_script(research_data)

        log("Generating SEO...")
        seo = generate_seo(topic, script)

        log("Generating thumbnail text...")
        generate_thumbnail_text(topic)

        log("Generating thumbnail image...")
        thumbnail_image = generate_thumbnail(seo["title"], topic)

        log("Generating background images...")
        image_paths, image_errors = generate_backgrounds(topic, script, num_images=4)
        if not image_paths:
            log(f"ERROR: No images — {image_errors}")
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
            hashtags=seo["hashtags"],
            thumbnail_path=thumbnail_image
        )

        log(f"SUCCESS: {video_url}")

    except Exception as e:
        import traceback
        log(f"ERROR: {str(e)}")
        log(f"TRACEBACK: {traceback.format_exc()}")


schedule.every().day.at("10:40").do(generate_and_upload)

if __name__ == "__main__":
    log("Scheduler started!")
    log(f"Timezone: Asia/Kolkata (IST)")
    log(f"Next run: {schedule.next_run()}")

    while True:
        schedule.run_pending()
        time.sleep(30)
