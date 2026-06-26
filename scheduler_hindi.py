# scheduler_hindi.py
import schedule
import time
import os
import datetime

LOG_FILE = "output/scheduler_hindi_log.txt"
POSTED_TODAY_FILE = "output/posted_today_hindi.txt"


def log(message):
    os.makedirs("output", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def get_posted_today():
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


def generate_and_upload_hindi():
    log("=== Hindi video generation shuru hua ===")

    try:
        # Step 1: Trending topic
        log("Hindi trending topic dhundh raha hai...")
        from agents_hindi.spy_agent import get_best_hindi_topic, get_hindi_trending_topics
        from agents_hindi.trending_agent import get_trending_topic

        best = get_best_hindi_topic()

        if best:
            topic = best['topic']
            log(f"Spy agent se topic mila: {topic} ({best['views']:,} views)")
        else:
            log("24 ghante mein koi video nahi mili, trending agent use kar raha hai...")
            topic = get_trending_topic(region_code="IN")
            log(f"Trending topic: {topic}")

        # Duplicate check
        posted_today = get_posted_today()
        if topic in posted_today:
            log(f"Ye topic aaj already post ho chuka hai: {topic}")
            all_topics = get_hindi_trending_topics()
            for t in all_topics:
                if t['topic'] not in posted_today:
                    topic = t['topic']
                    log(f"Alternative topic: {topic}")
                    break

        # Phase 2 — Competitor comparison (Hindi)
        log("Competitor comparison ho raha hai...")
        try:
            from agents_hindi.comparison_agent import compare_topic_hindi
            comparison = compare_topic_hindi(topic)
            comparison_insights = comparison.get("insights", {})
            if comparison_insights and not comparison_insights.get("error"):
                log(f"Comparison: avg views={comparison_insights.get('competitor_avg_views', 0):,}, "
                    f"best hour={comparison_insights.get('best_upload_hour_utc')} UTC")
            else:
                log("Comparison: data nahi mila, bina insights ke proceed kar rahe hain.")
                comparison_insights = {}
        except Exception as ce:
            log(f"Comparison skip: {ce}")
            comparison_insights = {}

        # Step 2: Research
        log("Research ho raha hai...")
        from agents.research_agent import research
        research_data = research(topic)

        # Step 3: Hindi Script (with comparison insights)
        log("Hindi script ban rahi hai...")
        from agents_hindi.script_agent import create_script
        script = create_script(research_data, topic=topic,
                               comparison_insights=comparison_insights)

        # Step 4: Hindi SEO (with comparison insights)
        log("Hindi SEO generate ho raha hai...")
        from agents_hindi.seo_agent import generate_seo
        seo = generate_seo(topic, script, comparison_insights=comparison_insights)
        log(f"Title: {seo['title']}")

        # Step 5: Thumbnail
        log("Thumbnail ban raha hai...")
        from agents.thumbnail_generator import generate_thumbnail
        thumbnail = generate_thumbnail(seo["title"], topic)

        # Step 6: Background images
        log("Background images fetch ho rahi hain...")
        from agents.image_agent import generate_backgrounds
        image_paths, errors = generate_backgrounds(topic, script, num_images=4)
        if not image_paths:
            log(f"Images nahi bani: {errors}")
            return

        # Step 7: Hindi Voice
        log("Hindi awaaz generate ho rahi hai...")
        from agents_hindi.voice_agent import generate_voice
        voice = generate_voice(script)

        # Step 8: Captions
        log("Captions ban rahe hain...")
        from agents.caption_agent import create_srt
        create_srt(script, voice)

        # Step 9: Video
        log("Video ban raha hai...")
        from agents.video_agent import create_video
        video = create_video()

        # Step 10: Upload
        log("YouTube Hindi channel par upload ho raha hai...")
        from agents_hindi.upload_agent import upload_video
        video_id, video_url = upload_video(
            video_path=video,
            title=seo["title"],
            description=seo["description"],
            hashtags=seo["hashtags"],
            thumbnail_path=thumbnail
        )

        mark_posted_today(topic)
        log(f"SUCCESS: Upload ho gaya! {video_url}")

    except Exception as e:
        import traceback
        log(f"ERROR: {str(e)}")
        log(f"TRACEBACK: {traceback.format_exc()}")


# Post 3 times per day
schedule.every().day.at("08:00").do(generate_and_upload_hindi)
schedule.every().day.at("13:00").do(generate_and_upload_hindi)
schedule.every().day.at("19:00").do(generate_and_upload_hindi)

if __name__ == "__main__":
    log("Hindi Scheduler shuru hua!")
    log(f"Schedule: 8 AM, 1 PM, 7 PM")
    log(f"Next run: {schedule.next_run()}")

    while True:
        schedule.run_pending()
        time.sleep(60)
