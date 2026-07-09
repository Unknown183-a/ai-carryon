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
    # Push updated posted_topics.txt to GitHub immediately
    try:
        from agents.data_persistence import backup_posted_topics
        backup_posted_topics()
    except Exception as e:
        log(f"posted_topics backup skipped: {e}")


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


_top_hours_cache = {"value": None, "computed_at": None}
_TOP_HOURS_CACHE_TTL_SECONDS = 180  # recompute at most every 3 minutes


def get_top_upload_hours(n=3, min_gap_hours=1):
    """
    Pick top N distinct upload hours by real velocity. No averaging.

    Cached for _TOP_HOURS_CACHE_TTL_SECONDS since the underlying query
    (get_peak_hours) does a full in-memory pass over every snapshot row —
    cheap today, but grows with snapshot count, and this function is now
    polled every 30s by the main loop. Caching keeps the poll loop's
    restart-resilience benefit without recomputing on every single cycle.
    """
    now_ts = datetime.datetime.utcnow().timestamp()
    cached = _top_hours_cache
    if cached["value"] is not None and cached["computed_at"] is not None:
        if now_ts - cached["computed_at"] < _TOP_HOURS_CACHE_TTL_SECONDS:
            return cached["value"]

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
            result = sorted(chosen)
            log(f"Top upload hours from real data (UTC): {result}")
            _top_hours_cache["value"] = result
            _top_hours_cache["computed_at"] = now_ts
            return result
    except Exception as e:
        log(f"Could not get top upload hours: {e}")
    fallback = [4, 12, 19]
    log(f"Using fallback upload hours (UTC): {fallback}")
    _top_hours_cache["value"] = fallback
    _top_hours_cache["computed_at"] = now_ts
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

    # --- Mutex lock: prevent overlapping generation runs ---
    lock_path = "output/generation.lock"
    if os.path.exists(lock_path):
        lock_age = time.time() - os.path.getmtime(lock_path)
        if lock_age < 1800:  # 30 min — generous vs. typical 5-15 min run
            log(f"Generation already in progress (lock age {lock_age:.0f}s) — skipping to avoid concurrent run")
            return
        else:
            log(f"Stale lock found (age {lock_age:.0f}s) — previous run likely crashed, proceeding")

    os.makedirs("output", exist_ok=True)
    with open(lock_path, "w") as f:
        f.write(str(time.time()))

    log("=== Starting scheduled video generation ===")
    try:
        from agents.checkpoint import (
            save_checkpoint, is_stage_done, get_stage_data,
            clear_checkpoint, list_checkpoints,
        )
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

        # Resume a crashed run if one exists, instead of always starting fresh
        pending = list_checkpoints()
        if pending:
            cp = pending[0]
            topic = cp["topic"]
            log(f"Resuming incomplete generation for topic: {topic} (last stage: {cp.get('last_stage')})")
        else:
            log("Fetching trending YouTube topic...")
            topic = get_fresh_trending_topic(region_code="US")
            log(f"Trending topic: {topic}")

        if is_stage_done(topic, "research"):
            research_data = get_stage_data(topic, "research")
            log("Resuming: research already done")
        else:
            log("Researching...")
            research_data = research(topic)
            save_checkpoint(topic, "research", research_data)

        if is_stage_done(topic, "script"):
            script = get_stage_data(topic, "script")
            log("Resuming: script already done")
        else:
            log("Writing script...")
            script = create_script(research_data)
            save_checkpoint(topic, "script", script)

        if is_stage_done(topic, "seo"):
            seo = get_stage_data(topic, "seo")
            log("Resuming: seo already done")
        else:
            log("Generating SEO...")
            seo = generate_seo(topic, script)
            save_checkpoint(topic, "seo", seo)

        log("Generating thumbnail text...")
        generate_thumbnail_text(topic)

        if is_stage_done(topic, "thumbnail") and get_stage_data(topic, "thumbnail") and os.path.exists(get_stage_data(topic, "thumbnail")):
            thumbnail_image = get_stage_data(topic, "thumbnail")
            log("Resuming: thumbnail already done")
        else:
            log("Generating thumbnail image...")
            thumbnail_image = generate_thumbnail(seo["title"], topic)
            save_checkpoint(topic, "thumbnail", thumbnail_image)

        if is_stage_done(topic, "images") and get_stage_data(topic, "images") and all(os.path.exists(p) for p in get_stage_data(topic, "images")):
            image_paths = get_stage_data(topic, "images")
            log("Resuming: images already done")
        else:
            log("Generating background images...")
            image_paths, image_errors = generate_backgrounds(topic, script, num_images=4)
            if not image_paths:
                log(f"ERROR: No images — {image_errors}")
                return
            save_checkpoint(topic, "images", image_paths)

        if is_stage_done(topic, "voice") and get_stage_data(topic, "voice") and os.path.exists(get_stage_data(topic, "voice")):
            voice_file = get_stage_data(topic, "voice")
            log("Resuming: voice already done")
        else:
            log("Generating voiceover...")
            voice_file = generate_voice(script)
            save_checkpoint(topic, "voice", voice_file)

        if not is_stage_done(topic, "captions"):
            log("Generating captions...")
            create_srt(script, voice_file)
            save_checkpoint(topic, "captions", True)
        else:
            log("Resuming: captions already done")

        if is_stage_done(topic, "video") and get_stage_data(topic, "video") and os.path.exists(get_stage_data(topic, "video")):
            video_file = get_stage_data(topic, "video")
            log("Resuming: video already rendered")
        else:
            log("Creating video...")
            video_file = create_video()
            save_checkpoint(topic, "video", video_file)

        if is_stage_done(topic, "upload"):
            video_id, video_url = get_stage_data(topic, "upload")
            log(f"Resuming: already uploaded previously — {video_url} — skipping re-upload")
        else:
            log("Uploading to YouTube...")
            video_id, video_url = upload_video(
                video_path=video_file,
                title=seo["title"],
                description=seo["description"],
                hashtags=seo["hashtags"],
                thumbnail_path=thumbnail_image
            )
            save_checkpoint(topic, "upload", [video_id, video_url])

        # Link this upload back to its AB title test, if any
        if seo.get("ab_winner"):
            try:
                from agents.database import db
                linked = db.link_ab_test_to_video(seo["ab_winner"], video_id)
                if linked:
                    log(f"Linked AB test to video_id {video_id}")
            except Exception as link_err:
                log(f"AB test link skipped: {link_err}")

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

        clear_checkpoint(topic)

        from agents.cleanup_agent import cleanup_after_upload
        cleanup_after_upload(video_file, log_fn=log)

    except Exception as e:
        import traceback
        log(f"ERROR: {str(e)}")
        log(f"TRACEBACK: {traceback.format_exc()}")
    finally:
        if os.path.exists(lock_path):
            os.remove(lock_path)


# Check every hour — generate+upload only when current hour matches a top velocity window
# NOTE: hourly schedule.at(":00") intentionally NOT used for generation —
# it only fires at the exact minute mark, so a Railway restart landing on
# that instant silently skips the whole hour with no catch-up. Generation
# is instead driven by a continuous poll in the main loop (see __main__),
# which checks every 30s whether we're in a top hour and haven't generated
# for it yet — resilient to restarts at any point during the window.


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
            from agents.close_ab_loop import close_loop
            close_loop(channel="english")
            log("Closed AB-title loop (actual_views_24h updated where due)")
        except Exception as ce:
            log(f"close_ab_loop skipped: {ce}")

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

def comment_reply_job():
    try:
        from agents.comment_reply_agent import process_comments
        process_comments(log_fn=log)
    except Exception as e:
        log(f"Comment reply job error: {e}")

schedule.every(1).hours.do(comment_reply_job)

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
        from agents.data_persistence import restore_view_history, restore_ab_log, restore_posted_topics
        restore_view_history()
        restore_ab_log()
        restore_posted_topics()
        log("View history, AB log, and posted topics restored from GitHub")
    except Exception as e:
        log(f"Restore from GitHub skipped: {e}")

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

    generated_hours_today = set()
    last_date = datetime.datetime.utcnow().date()

    while True:
        schedule.run_pending()

        now = datetime.datetime.utcnow()
        if now.date() != last_date:
            generated_hours_today = set()
            last_date = now.date()

        try:
            should_run, reason = should_upload_now()
            if should_run and now.hour not in generated_hours_today:
                posted_today = get_recent_topics(hours=24)
                if len(posted_today) >= 3:
                    log(f"Poll check: {reason}, but daily cap reached ({len(posted_today)} posted in last 24h) — skipping")
                    generated_hours_today.add(now.hour)
                else:
                    log(f"Poll trigger: {reason}")
                    generated_hours_today.add(now.hour)
                    generate_and_upload(force=True)
        except Exception as pe:
            log(f"Poll check error: {pe}")

        time.sleep(30)
