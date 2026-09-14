# scheduler_gaming.py
"""
Gaming pipeline: Twitch clip -> script -> SEO -> voice -> real clip footage
-> captions -> upload. Deduplicates against gaming_posted_clips in the DB.

Run locally: python scheduler_gaming.py
Deployed:    .github/workflows/gaming-scheduler.yml (cron, no server needed
             — unlike cricket's Render /trigger pattern, this runs the
             script directly as a scheduled GitHub Actions job).
"""
import os
from dotenv import load_dotenv
load_dotenv()

from agents_gaming.database import db as gaming_db, db_init_error as gaming_db_init_error

DAILY_UPLOAD_CAP = int(os.getenv("GAMING_DAILY_UPLOAD_CAP", "5"))


def run_gaming_cycle():
    import traceback
    try:
        return _run_gaming_cycle_inner()
    except Exception as e:
        print(f"GAMING PIPELINE CRASHED: {e}")
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


def _check_daily_cap():
    from datetime import datetime, timezone
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        stored_date = gaming_db.get_meta("gaming_upload_date")
        count = int(gaming_db.get_meta("gaming_upload_count") or 0)
        if stored_date != today:
            gaming_db.set_meta("gaming_upload_date", today)
            gaming_db.set_meta("gaming_upload_count", "0")
            count = 0
        return count
    except Exception as e:
        print(f"Daily cap check failed, assuming 0: {e}")
        return 0


def _increment_daily_cap():
    from datetime import datetime, timezone
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        count = int(gaming_db.get_meta("gaming_upload_count") or 0) + 1
        gaming_db.set_meta("gaming_upload_date", today)
        gaming_db.set_meta("gaming_upload_count", str(count))
    except Exception as e:
        print(f"Daily cap increment failed: {e}")


def _run_gaming_cycle_inner():
    from datetime import datetime, timezone

    from agents_gaming.trending_agent import get_all_topics
    from agents_gaming.clip_finder import find_best_unposted_clip
    from agents_gaming.research_agent import get_summary_for_clip
    from agents_gaming.script_agent import create_gaming_script
    from agents_gaming.seo_agent import generate_seo
    from agents_gaming.video_clip_agent import get_gaming_background_clip
    from agents_gaming.upload_agent import upload_video

    from agents.voice_agent import generate_voice
    from agents.caption_agent import create_srt
    from agents.video_agent import _create_video_from_pexels_clips

    if gaming_db is None:
        return {"status": "error", "error": f"Gaming DB unavailable: {gaming_db_init_error}"}

    uploads_today = _check_daily_cap()
    if uploads_today >= DAILY_UPLOAD_CAP:
        print(f"Daily gaming upload cap reached ({uploads_today}/{DAILY_UPLOAD_CAP}) — skipping.")
        return {"status": "daily_cap_reached", "uploads_today": uploads_today}

    posted = gaming_db.get_all_posted_clip_ids()
    candidates = get_all_topics()
    if not candidates:
        print("No candidate clips found this cycle (check TWITCH_FOLLOWED_STREAMERS / "
              "TWITCH_TRACKED_GAMES and Twitch app credentials).")
        return {"status": "no_candidates"}

    clip = find_best_unposted_clip(candidates, posted)
    if not clip:
        print("All candidate clips already posted this cycle.")
        return {"status": "no_new_clip"}

    print(f"Selected clip: '{clip.get('title')}' by {clip.get('broadcaster_name')} "
          f"({clip.get('view_count', 0):,} views)")

    summary, structured = get_summary_for_clip(clip)

    script = create_gaming_script(summary, structured)
    print(f"Script ({len(script.split())} words): {script[:80]}...")

    title, description, hashtags = generate_seo(structured, script)
    print(f"Title: {title}")

    generate_voice(script, output_path="output/voice.mp3")
    create_srt(script, audio_path="output/voice.mp3")

    print("Downloading Twitch clip footage...")
    clip_paths = get_gaming_background_clip(clip)

    video_path = _create_video_from_pexels_clips(
        clip_paths, "output/voice.mp3", "output/captions.srt",
        music_path=None,  # the clip has its own game audio under the voiceover
    )

    video_id, video_url = upload_video(video_path, title, description, hashtags)
    print(f"Uploaded: {video_url}")

    gaming_db.mark_posted(clip["id"], clip.get("title", ""), clip.get("broadcaster_name", ""))
    gaming_db.upsert_video(
        video_id=video_id,
        title=title,
        published=datetime.now(timezone.utc).isoformat(),
        clip_id=clip["id"],
    )
    _increment_daily_cap()

    return {"status": "uploaded", "video_url": video_url, "title": title}


if __name__ == "__main__":
    result = run_gaming_cycle()
    print(result)
