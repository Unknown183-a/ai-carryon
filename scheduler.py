import schedule
import time
import os
import datetime

LOG_FILE = "output/scheduler_log.txt"
POSTED_FILE = "output/posted_topics.txt"


def log(message):
    os.makedirs("output", exist_ok=True)
    utc_now = datetime.datetime.utcnow()
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    timestamp = ist_now.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp} IST] {message}"
    print(entry, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def get_recent_topics(hours=24):
    if not os.path.exists(POSTED_FILE):
        return []

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
    recent = []

    with open(POSTED_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or "|" not in line:
                continue
            ts_str, topic = line.split("|", 1)
            try:
                ts = datetime.datetime.fromisoformat(ts_str)
            except ValueError:
                continue
            if ts >= cutoff:
                recent.append(topic.lower().strip())

    return recent


def mark_posted(topic):
    # Write to SQLite
    try:
        from agents.database import db
        db.mark_posted(topic, channel="english")
    except Exception as e:
        log(f"DB mark_posted error: {e}")
    # Also write to file (backup)
    os.makedirs("output", exist_ok=True)
    ts = datetime.datetime.utcnow().isoformat()
    with open(POSTED_FILE, "a") as f:
        f.write(f"{ts}|{topic}\n")


def get_fresh_trending_topic(region_code="US", max_attempts=5):
    from agents.trending_agent import get_trending_topic
    from agents.saturation_agent import check_saturation

    recent_topics = get_recent_topics(hours=24)

    for attempt in range(max_attempts):
        topic = get_trending_topic(region_code=region_code)

        if topic.lower().strip() in recent_topics:
            log(f"Topic already posted in last 24h, retrying ({attempt+1}/{max_attempts}): {topic}")
            continue

        # Phase 1.5 — Saturation check
        saturation = check_saturation(topic)
        log(f"Saturation check: score={saturation['opportunity_score']} — {saturation['reason']}")

        if not saturation["proceed"]:
            log(f"Topic too saturated, retrying ({attempt+1}/{max_attempts}): {topic}")
            continue

        return topic

    # Exhausted retries — use last topic anyway
    return topic + " - extra"


def get_top_upload_hours(n=3, min_gap_hours=1):
    """Pick top N distinct upload hours by real velocity. No averaging."""
    try:
        from agents.database import db
        peak_hours = db.get_peak_hours()
        candidates = sorted(
            [{"hour": h, "avg_velocity": data["avg_velocity"]}
             for h, data in peak_hours.items()
             if data["sample_count"] >= 2 and data["avg_velocity"] > 0],
            key=lambda x: x["avg_velocity"], reverse=True
        )
        chosen = []
        for c in candidates:
            h = c["hour"]
            too_close = any(
                min(abs(h - ch), 24 - abs(h - ch)) < min_gap_hours
                for ch in chosen
            )
            if not too_close:
                chosen.append(h)
            if len(chosen) == n:
                break
        if len(chosen) >= 1:
            log(f"Top upload hours from real data (UTC): {sorted(chosen)}")
            return sorted(chosen)
    except Exception as e:
        log(f"Could not get top upload hours: {e}")
    fallback = [4, 12, 19]
    log(f"Using fallback upload hours (UTC): {fallback}")
    return fallback


def should_upload_now():
    """Return (True, reason) if current UTC hour matches a top upload slot."""
    top_hours = get_top_upload_hours(n=3, min_gap_hours=1)
    current_hour = __import__("datetime").datetime.utcnow().hour
    if current_hour in top_hours:
        return True, f"Hour {current_hour:02d}:00 UTC is in top slots {top_hours}"
    return False, f"Hour {current_hour:02d}:00 UTC not in top slots {top_hours}"


def generate_and_upload(force=False):
    if not force:
        should_run, reason = should_upload_now()
        log(f"Schedule check: {reason}")
        if not should_run:
            return

        posted_today = get_recent_topics(hours=24)
        if len(posted_today) >= 3:
            log("Daily cap reached (3 videos) — skipping this hour")
            return
    else:
        log("FORCE MODE: bypassing schedule gate and daily cap")

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

        log("Fetching trending YouTube topic...")
        topic = get_fresh_trending_topic(region_code="US")
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

        log("Posting to Instagram Reels...")
        try:
            from agents.instagram_agent import post_reel
            caption = f"{seo['title']}\n\n{seo['description']}\n\n{' '.join(['#' + h for h in seo['hashtags']])}"
            insta_id = post_reel(video_file, caption)
            log(f"Instagram posted! ID: {insta_id}")
        except Exception as insta_err:
            log(f"Instagram post failed (YouTube still uploaded): {insta_err}")

        mark_posted(topic)
        log(f"SUCCESS: YouTube: {video_url}")

        from agents.cleanup_agent import cleanup_after_upload
        cleanup_after_upload(video_file, log_fn=log)

    except Exception as e:
        import traceback
        log(f"ERROR: {str(e)}")
        log(f"TRACEBACK: {traceback.format_exc()}")


# Check every hour — generate+upload only when current hour matches a top velocity window
schedule.every().hour.at(":00").do(generate_and_upload)


def track_views_job():
    has_secrets = os.path.exists("client_secrets.json") or os.environ.get("YOUTUBE_CLIENT_SECRETS_B64")
    if not has_secrets:
        print("[SKIP] No YouTube credentials found (file or env var) — view tracking disabled")
        return
    log("=== Tracking video view history ===")
    try:
        from agents.view_tracker_agent import track_views
        history = track_views()
        log(f"Tracked {len(history)} videos")
        try:
            from agents.data_persistence import backup_view_history
            backup_view_history()
            from agents.data_persistence import backup_sqlite_db
            backup_sqlite_db()
        except Exception as be:
            log(f"Backup skipped: {be}")
    except Exception as e:
        import traceback
        log(f"ERROR (view tracking): {str(e)}")
        log(f"TRACEBACK: {traceback.format_exc()}")


schedule.every(1).hours.do(track_views_job)

if __name__ == "__main__":
    log("Scheduler started!")
    log("Generation: adaptive — top 3 velocity hours, max 3/day")
    log("View tracking: every 1 hour")

    try:
        from agents.cleanup_agent import sweep_old_videos
        sweep_old_videos(max_age_hours=24, log_fn=log)
    except Exception as e:
        log(f"Cleanup skipped: {e}")

    # Step 1: Restore view_history.json from GitHub
    try:
        from agents.data_persistence import restore_view_history
        restore_view_history()
        log("View history restored from GitHub")
    except Exception as e:
        log(f"View history restore skipped: {e}")

    # Step 2: Migrate JSON into SQLite so velocity data is available
    try:
        from agents.database import db
        result = db.migrate_from_json(
            view_history_path="output/view_history.json",
            ab_log_path="output/title_ab_log.json",
            posted_path="output/posted_topics.txt",
        )
        log(f"SQLite rebuilt from GitHub backup: {result}")
    except Exception as e:
        log(f"SQLite migration skipped: {e}")

    # Step 3: Show which hours will be used today
    try:
        hours = get_top_upload_hours(n=3, min_gap_hours=1)
        log(f"Upload slots today (UTC): {hours}")
    except Exception as e:
        log(f"Could not compute upload hours: {e}")

    # Step 4: Initial view tracking snapshot
    track_views_job()

    utc_now = datetime.datetime.utcnow()
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    log(f"Current IST time: {ist_now.strftime('%H:%M:%S')}")
    log(f"Next check (UTC): {schedule.next_run()}")

    import threading
    if os.environ.get("TEST_UPLOAD_ON_START", "false").lower() == "true":
        log("TEST MODE: will force generate_and_upload(force=True) in 5 minutes — bypassing schedule gate")
        threading.Timer(300, lambda: generate_and_upload(force=True)).start()

    while True:
        schedule.run_pending()
        time.sleep(30)
