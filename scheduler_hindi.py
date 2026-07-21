# scheduler_hindi.py — single-run entrypoint for Cloud Run Jobs
#
# Same refactor as scheduler.py: no more infinite loop / schedule library /
# GitHub restore-backup dance. One pass per invocation, triggered hourly by
# Cloud Scheduler. See scheduler.py's module docstring for the full rationale.

import os
import datetime

LOG_FILE = "output/scheduler_hindi_log.txt"

# How many videos per day to aim for (fully adaptive)
VIDEOS_PER_DAY = 3


def log(message):
    os.makedirs("output", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def get_posted_today():
    from agents.database import db
    return db.get_recent_posted(hours=24, channel="hindi")


def get_posted_count_today():
    return len(get_posted_today())


def mark_posted_today(topic):
    from agents.database import db
    try:
        db.mark_posted(topic, channel="hindi")
    except Exception as e:
        log(f"DB mark_posted error: {e}")


def get_adaptive_hours():
    """Top N best upload hours from real Hindi velocity data, falling back
    to spread-out defaults if not enough data yet. No longer cached — this
    runs once per process now, so the old TTL cache is unnecessary."""
    try:
        from agents_hindi.velocity_agent import get_best_upload_windows_hindi
        windows = get_best_upload_windows_hindi(top_n=VIDEOS_PER_DAY)
        good_windows = [w for w in windows if w["sample_count"] >= 3]
        if len(good_windows) >= VIDEOS_PER_DAY:
            hours = sorted([w["hour"] for w in good_windows[:VIDEOS_PER_DAY]])
            log(f"Adaptive hours from real data (UTC): {hours}")
            return hours
    except Exception as e:
        log(f"Could not get adaptive hours: {e}")

    fallback = [2, 7, 13]  # UTC hours ≈ 7:30AM, 12:30PM, 6:30PM IST
    log(f"Not enough Hindi data yet — using fallback hours (UTC): {fallback}")
    return fallback


def should_generate_now():
    if get_posted_count_today() >= VIDEOS_PER_DAY:
        return False, "Daily quota reached"

    adaptive_hours = get_adaptive_hours()
    current_hour = datetime.datetime.utcnow().hour

    if current_hour in adaptive_hours:
        # Check 1 hour minimum gap from last upload
        try:
            from agents.database import db
            from datetime import datetime, timezone
            last = db.get_meta("last_upload_hour_hindi")
            if last:
                gap = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 3600
                if gap < 1.0:
                    return False, f"Only {gap:.1f}h since last Hindi upload — need 1h gap"
        except Exception:
            pass
        return True, f"Current hour {current_hour:02d}:00 UTC is in best hours {adaptive_hours}"

    return False, f"Current hour {current_hour:02d}:00 UTC not in best hours {adaptive_hours}"


def generate_and_upload_hindi(force=False):
    from agents.database import db

    if force:
        log("Schedule check: BYPASSED (FORCE_GENERATE)")
    else:
        should_run, reason = should_generate_now()
        log(f"Schedule check: {reason}")
        if not should_run:
            return

    acquired, age = db.try_acquire_lock("generation_hindi", ttl_seconds=1800)
    if not acquired:
        log(f"Generation already in progress elsewhere (lock age {age:.0f}s) — skipping")
        return

    log("=== Hindi video generation shuru hua ===")

    try:
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

        posted_today = get_posted_today()
        if topic in posted_today:
            log(f"Ye topic aaj already post ho chuka hai: {topic}")
            all_topics = get_hindi_trending_topics()
            for t in all_topics:
                if t['topic'] not in posted_today:
                    topic = t['topic']
                    log(f"Alternative topic: {topic}")
                    break

        log("Saturation check ho raha hai...")
        try:
            from agents_hindi.saturation_agent import check_saturation_hindi
            saturation = check_saturation_hindi(topic)
            log(f"Saturation: score={saturation['opportunity_score']} — {saturation['reason']}")
        except Exception as se:
            log(f"Saturation check skip: {se}")

        log("Competitor comparison ho raha hai...")
        try:
            from agents_hindi.comparison_agent import compare_topic_hindi
            comparison = compare_topic_hindi(topic)
            comparison_insights = comparison.get("insights", {})
            if comparison_insights and not comparison_insights.get("error"):
                log(f"Comparison: avg views={comparison_insights.get('competitor_avg_views', 0):,}")
            else:
                comparison_insights = {}
        except Exception as ce:
            log(f"Comparison skip: {ce}")
            comparison_insights = {}

        log("Research ho raha hai...")
        from agents.research_agent import research
        research_data = research(topic)

        log("Hindi script ban rahi hai...")
        from agents_hindi.script_agent import create_script
        script = create_script(research_data, topic=topic,
                               comparison_insights=comparison_insights)

        log("A/B title testing ho raha hai...")
        ab_winner_title = None
        try:
            from agents_hindi.ab_title_agent import get_best_title_hindi
            ab_result = get_best_title_hindi(topic, script)
            ab_winner_title = ab_result["winner"]["title"]
            log(f"A/B winner: {ab_winner_title} (score: {ab_result['winner']['score']}/10)")
        except Exception as ae:
            log(f"A/B title test skip: {ae}")

        log("Hindi SEO generate ho raha hai...")
        from agents_hindi.seo_agent import generate_seo
        seo = generate_seo(topic, script, comparison_insights=comparison_insights)
        if ab_winner_title:
            seo["title"] = ab_winner_title
        log(f"Title: {seo['title']}")

        log("Thumbnail ban raha hai...")
        from agents.thumbnail_generator import generate_thumbnail
        thumbnail = generate_thumbnail(seo["title"], topic)

        log("Background images fetch ho rahi hain (generative mode)...")
        from agents.generative_image_agent import generate_backgrounds
        image_paths, errors = generate_backgrounds(topic, script, num_images=4, mode="generative")
        if not image_paths:
            log(f"Images nahi bani: {errors}")
            return

        log("Hindi awaaz generate ho rahi hai...")
        from agents_hindi.voice_agent import generate_voice
        voice = generate_voice(script)

        log("Captions ban rahe hain...")
        from agents.caption_agent import create_srt
        create_srt(script, voice)

        log("Video ban raha hai...")
        from agents.video_agent import create_video
        video = create_video()

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
        try:
            from agents.adaptive_scheduler import mark_upload_done
            mark_upload_done("hindi")
        except Exception:
            pass
        log(f"SUCCESS: Upload ho gaya! {video_url}")

        from agents.cleanup_agent import cleanup_after_upload
        cleanup_after_upload(video, log_fn=log)

    except Exception as e:
        import traceback
        log(f"ERROR: {str(e)}")
        log(f"TRACEBACK: {traceback.format_exc()}")
    finally:
        db.release_lock("generation_hindi")


def track_views_hindi_job():
    log("=== Hindi view history track ho raha hai ===")
    try:
        from agents_hindi.view_tracker_agent import track_views_hindi
        history = track_views_hindi()
        log(f"Tracked {len(history)} Hindi videos")

        try:
            from agents.close_ab_loop import close_loop
            close_loop(channel="hindi")
            log("Closed AB-title loop (actual_views_24h updated where due)")
        except Exception as ce:
            log(f"close_ab_loop skipped: {ce}")
    except Exception as e:
        import traceback
        log(f"ERROR (Hindi view tracking): {str(e)}")
        log(f"TRACEBACK: {traceback.format_exc()}")


def comment_reply_job_hindi():
    try:
        from agents_hindi.comment_reply_agent import process_comments_hindi
        process_comments_hindi(log_fn=log)
    except Exception as e:
        log(f"Comment reply job error: {e}")


def main():
    log("Hindi Scheduler run started (Cloud Run Job — single pass, Fully Adaptive Mode)")

    try:
        from agents.cleanup_agent import sweep_old_videos
        sweep_old_videos(max_age_hours=24, log_fn=log)
    except Exception as e:
        log(f"Cleanup skipped: {e}")

    track_views_hindi_job()
    comment_reply_job_hindi()

    if os.environ.get("FORCE_GENERATE", "false").lower() == "true":
        generate_and_upload_hindi(force=True)
        return

    generate_and_upload_hindi(force=False)


if __name__ == "__main__":
    main()
