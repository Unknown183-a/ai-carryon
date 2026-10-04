# scheduler_bhakti.py — single-run entrypoint for the Bhakti (devotional) channel
#
# Fifth pipeline, following the same single-pass-per-invocation pattern as
# scheduler.py / scheduler_hindi.py: one full generate+upload attempt per
# run, triggered hourly by Cloud Scheduler / Render cron / Railway cron.

import os
import datetime

LOG_FILE = "output/scheduler_bhakti_log.txt"

# How many videos per day to aim for (fully adaptive)
VIDEOS_PER_DAY = int(os.environ.get("BHAKTI_VIDEOS_PER_DAY", "6"))

# "narrated" (default): Hindi voiceover + captions over a ducked bhajan track.
# "music_only": previous behaviour (no voice, no captions, bhajan only).
BHAKTI_MODE = os.environ.get("BHAKTI_MODE", "narrated").lower()


def log(message):
    os.makedirs("output", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def get_posted_today():
    from agents.database import db
    return db.get_recent_posted(hours=24, channel="bhakti")


def get_posted_count_today():
    return len(get_posted_today())


def mark_posted_today(topic):
    from agents.database import db
    try:
        db.mark_posted(topic, channel="bhakti")
    except Exception as e:
        log(f"DB mark_posted error: {e}")


def get_adaptive_hours():
    """Top N best upload hours from real Bhakti velocity data, falling
    back to devotional-peak defaults (early morning Brahma muhurta and
    evening aarti time) for any slots not yet backed by real data."""
    # UTC ≈ 6:00/7:30 AM IST (morning puja) and 7:00 PM IST (evening aarti)
    fallback = [0, 2, 13]
    MIN_GOOD_WINDOWS = 3

    try:
        from agents_bhakti.velocity_agent import get_best_upload_windows_bhakti
        windows = get_best_upload_windows_bhakti(top_n=VIDEOS_PER_DAY)
        good_windows = [w for w in windows if w["sample_count"] >= 3]

        if len(good_windows) >= MIN_GOOD_WINDOWS:
            hours = [w["hour"] for w in good_windows[:VIDEOS_PER_DAY]]
            for h in fallback:
                if len(hours) >= VIDEOS_PER_DAY:
                    break
                if h not in hours:
                    hours.append(h)
            hours = sorted(hours)
            log(f"Adaptive hours (real+fallback mix, UTC): {hours}")
            return hours
    except Exception as e:
        log(f"Could not get adaptive hours: {e}")

    log(f"Not enough Bhakti data yet — using fallback hours (UTC): {fallback}")
    return fallback


def should_generate_now():
    if get_posted_count_today() >= VIDEOS_PER_DAY:
        return False, "Daily quota reached"

    adaptive_hours = get_adaptive_hours()
    import datetime as _dt
    current_hour = _dt.datetime.utcnow().hour

    if current_hour in adaptive_hours:
        try:
            from agents.database import db
            from datetime import datetime, timezone
            last = db.get_meta("last_upload_hour_bhakti")
            if last:
                gap = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 3600
                if gap < 1.0:
                    return False, f"Only {gap:.1f}h since last Bhakti upload — need 1h gap"
        except Exception:
            pass
        return True, f"Current hour {current_hour:02d}:00 UTC is in best hours {adaptive_hours}"

    return False, f"Current hour {current_hour:02d}:00 UTC not in best hours {adaptive_hours}"


def generate_and_upload_bhakti(force=False):
    from agents.database import db

    if force:
        log("Schedule check: BYPASSED (FORCE_GENERATE)")
    else:
        should_run, reason = should_generate_now()
        log(f"Schedule check: {reason}")
        if not should_run:
            return

    acquired, age = db.try_acquire_lock("generation_bhakti", ttl_seconds=1800)
    if not acquired:
        log(f"Generation already in progress elsewhere (lock age {age:.0f}s) — skipping")
        return

    log("=== Bhakti video generation shuru hua ===")

    try:
        log("Bhakti topic dhundh raha hai...")
        from agents_bhakti.trending_agent import get_trending_topic
        topic = get_trending_topic(region_code="IN")
        log(f"Topic: {topic}")

        posted_today = get_posted_today()
        if topic in posted_today:
            log(f"Ye topic aaj already post ho chuka hai: {topic} — retrying trending_agent")
            topic = get_trending_topic(region_code="IN")
            log(f"Alternative topic: {topic}")

        log("Saturation check ho raha hai...")
        try:
            from agents_bhakti.saturation_agent import check_saturation_bhakti
            saturation = check_saturation_bhakti(topic)
            log(f"Saturation: score={saturation['opportunity_score']} — {saturation['reason']}")
        except Exception as se:
            log(f"Saturation check skip: {se}")

        log("Competitor comparison ho raha hai...")
        try:
            from agents_bhakti.comparison_agent import compare_topic_bhakti
            comparison = compare_topic_bhakti(topic)
            comparison_insights = comparison.get("insights", {})
            if comparison_insights and not comparison_insights.get("error"):
                log(f"Comparison: avg views={comparison_insights.get('competitor_avg_views', 0):,}")
            else:
                comparison_insights = {}
        except Exception as ce:
            log(f"Comparison skip: {ce}")
            comparison_insights = {}

        log("Devotional research ho raha hai...")
        from agents_bhakti.research_agent import research
        research_data = research(topic)

        log("Bhakti script ban rahi hai...")
        from agents_bhakti.script_agent import create_script
        script = create_script(research_data, topic=topic,
                               comparison_insights=comparison_insights)

        log("A/B title testing ho raha hai...")
        ab_winner_title = None
        try:
            from agents_bhakti.ab_title_agent import get_best_title_bhakti
            ab_result = get_best_title_bhakti(topic, script)
            ab_winner_title = ab_result["winner"]["title"]
            log(f"A/B winner: {ab_winner_title} (score: {ab_result['winner']['score']}/10)")
        except Exception as ae:
            log(f"A/B title test skip: {ae}")

        log("Bhakti SEO generate ho raha hai...")
        from agents_bhakti.seo_agent import generate_seo
        seo = generate_seo(topic, script, comparison_insights=comparison_insights)
        if ab_winner_title:
            seo["title"] = ab_winner_title
        log(f"Title: {seo['title']}")

        log("Thumbnail ban raha hai...")
        from agents_bhakti.thumbnail_agent import generate_thumbnail
        thumbnail = generate_thumbnail(seo["title"], topic)

        # Hook Engine: reverent, topic-relevant opening clip (bhakti profile only allows
        # emotional/mystery/curiosity hooks and blocks dramatic/violent/deity imagery).
        # Never blocks the run: no suitable hook -> hook=None -> renders as before.
        hook = None
        try:
            log("Hook clip select ho raha hai...")
            from agents.hook_engine import select_hook
            from agents_bhakti.model_invoke_agent_bhakti import safe_invoke as _hook_invoke
            hook = select_hook(topic, script, "bhakti", invoke=_hook_invoke,
                               meta_get=db.get_meta, meta_set=db.set_meta)
            log(f"Hook: {hook['clip_id']} ({hook['duration']}s, relevance {hook['relevance']:.2f})"
                if hook else "Hook: koi suitable nahi - normal opening")
        except Exception as he:
            log(f"Hook engine skip: {he}")

        log("Pexels devotional video clips fetch ho rahe hain...")
        from agents_bhakti.image_agent import generate_background_clips, generate_backgrounds
        image_paths, errors = generate_background_clips(topic, script, num_clips=4)
        if len(image_paths) < 2:
            log(f"Bahut kam Pexels clips mile ({errors}) — static images par fallback ho raha hai...")
            image_paths, errors = generate_backgrounds(topic, script, num_images=4)
            use_pexels = False
        else:
            use_pexels = True
        if not image_paths:
            log(f"Images nahi bani: {errors}")
            return

        log("Bhakti background music dhoond rahe hain...")
        from agents_bhakti.music_agent import get_background_music
        music = get_background_music(topic, seo["title"])
        if not music:
            raise RuntimeError("No background music track found — aborting rather than uploading a silent video")
        if music["license"] != "Creative Commons 0":
            seo["description"] += (
                f"\n\nMusic: \"{music['name']}\" by {music['author']} "
                f"({music['license']}) - {music['url']}"
            )

        if BHAKTI_MODE == "music_only":
            log("Video ban raha hai (music-only, no narration)...")
            from agents_bhakti.silent_video_agent import create_silent_music_video
            video = create_silent_music_video(music_path=music["path"],
                                              hook=hook if use_pexels else None)
        else:
            log("Hindi bhakti awaaz generate ho rahi hai...")
            from agents_bhakti.voice_agent import generate_voice
            voice = generate_voice(script)

            log("Captions ban rahe hain...")
            from agents.caption_agent import create_srt
            create_srt(script, voice)

            log("Video ban raha hai (voiceover + bhajan background)...")
            if use_pexels:
                from agents_bhakti.narrated_video_agent import create_narrated_music_video
                video = create_narrated_music_video(music_path=music["path"], audio_path=voice,
                                                    hook=hook)
            else:
                from agents.video_agent import create_video
                video = create_video(use_pexels_clips=False, music_path=music["path"])

        log("YouTube Bhakti channel par upload ho raha hai...")
        from agents_bhakti.upload_agent import upload_video
        video_id, video_url = upload_video(
            video_path=video,
            title=seo["title"],
            description=seo["description"],
            hashtags=seo["hashtags"],
            thumbnail_path=thumbnail
        )

        if hook and use_pexels:
            from agents.hook_engine import record_usage as record_hook_usage
            record_hook_usage(hook, topic, "bhakti", db.get_meta, db.set_meta, video_id)

        mark_posted_today(topic)
        try:
            from agents.adaptive_scheduler import mark_upload_done
            mark_upload_done("bhakti")
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
        db.release_lock("generation_bhakti")


def track_views_bhakti_job():
    log("=== Bhakti view history track ho raha hai ===")
    try:
        from agents_bhakti.view_tracker_agent import track_views_bhakti
        history = track_views_bhakti()
        log(f"Tracked {len(history)} Bhakti videos")

        try:
            from agents.close_ab_loop import close_loop
            close_loop(channel="bhakti")
            log("Closed AB-title loop (actual_views_24h updated where due)")
        except Exception as ce:
            log(f"close_ab_loop skipped: {ce}")
    except Exception as e:
        import traceback
        log(f"ERROR (Bhakti view tracking): {str(e)}")
        log(f"TRACEBACK: {traceback.format_exc()}")


def comment_reply_job_bhakti():
    """Daily comment replies (19:00-23:59 IST, once per IST day; evening aarti
    time suits a devotional audience). Gate + bookkeeping live in
    agents/comment_engine.py. Never raises."""
    try:
        from agents_bhakti.comment_reply_agent import run_scheduled
        run_scheduled(log_fn=log)
    except Exception as e:
        log(f"Comment reply job error: {e}")


def main():
    log("Bhakti Scheduler run started (single pass, Fully Adaptive Mode)")

    from agents_bhakti.model_invoke_agent_bhakti import reset_groq_budget
    reset_groq_budget()

    try:
        from agents.cleanup_agent import sweep_old_videos
        sweep_old_videos(max_age_hours=24, log_fn=log)
    except Exception as e:
        log(f"Cleanup skipped: {e}")

    track_views_bhakti_job()
    comment_reply_job_bhakti()
    # Fresh Groq budget for generation (the comment job shares it).
    reset_groq_budget()

    if os.environ.get("FORCE_GENERATE", "false").lower() == "true":
        generate_and_upload_bhakti(force=True)
        return

    generate_and_upload_bhakti(force=False)


if __name__ == "__main__":
    main()
