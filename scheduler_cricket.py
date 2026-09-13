# scheduler_cricket.py
"""
Cricket pipeline: finished match -> summary -> script -> SEO -> voice ->
captions -> video -> upload. Deduplicates against output/cricket_posted.json.

Run locally: python scheduler_cricket.py
Deployed:    called by app_cricket.py's /trigger endpoint
"""
import os
import json
from dotenv import load_dotenv
load_dotenv()

from agents_cricket.database import db as cricket_db, db_init_error as cricket_db_init_error

VIEW_TRACK_INTERVAL_SECONDS = 55 * 60  # ~hourly, throttled since /trigger fires every ~20 min
DAILY_UPLOAD_CAP = 5  # max cricket uploads per day, stored in cricket_db (survives restarts)


def run_cricket_cycle():
    import traceback
    try:
        return _run_cricket_cycle_inner()
    except Exception as e:
        print(f"CRICKET PIPELINE CRASHED: {e}")
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


def _maybe_track_views():
    """Runs cricket view tracking at most once per VIEW_TRACK_INTERVAL_SECONDS,
    so every /trigger ping (every ~20 min) doesn't burn YouTube API quota."""
    from datetime import datetime, timezone

    try:
        last = cricket_db.get_meta("last_view_track_at")
        if last:
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
            if elapsed < VIEW_TRACK_INTERVAL_SECONDS:
                return
        from agents_cricket.view_tracker_agent import track_views_cricket
        track_views_cricket()
        cricket_db.set_meta("last_view_track_at", datetime.now(timezone.utc).isoformat())
    except Exception as e:
        print(f"Cricket view tracking skipped: {e}")


def _check_daily_cap():
    """Returns today's upload count so far, resetting the counter if the
    stored date isn't today. Persisted in cricket_db so it survives Render
    restarts between /trigger calls."""
    from datetime import datetime, timezone
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        stored_date = cricket_db.get_meta("cricket_upload_date")
        count = int(cricket_db.get_meta("cricket_upload_count") or 0)
        if stored_date != today:
            cricket_db.set_meta("cricket_upload_date", today)
            cricket_db.set_meta("cricket_upload_count", "0")
            count = 0
        return count
    except Exception as e:
        print(f"Daily cap check failed, assuming 0: {e}")
        return 0


def _increment_daily_cap():
    from datetime import datetime, timezone
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        count = int(cricket_db.get_meta("cricket_upload_count") or 0) + 1
        cricket_db.set_meta("cricket_upload_date", today)
        cricket_db.set_meta("cricket_upload_count", str(count))
    except Exception as e:
        print(f"Daily cap increment failed: {e}")


def _run_cricket_cycle_inner():
    from agents_cricket.trending_agent import get_all_topics
    from agents_cricket.research_agent import get_summary_for_topic
    from agents_cricket.script_agent import create_cricket_script
    from agents_cricket.seo_agent import generate_cricket_seo
    from agents_cricket.ab_title_agent import get_best_title_cricket
    from agents_cricket.saturation_agent import rank_topics_by_opportunity
    from agents_cricket.adaptive_scheduler import should_upload_now_cricket, mark_upload_done_cricket
    from agents_cricket.image_agent import generate_backgrounds
    from agents_cricket.upload_agent import upload_video
    from agents_cricket.voice_agent import generate_voice
    from agents.caption_agent import create_srt
    from agents_cricket.video_agent import create_video
    from datetime import datetime, timezone

    if cricket_db is None:
        return {"status": "error", "error": f"Cricket DB unavailable: {cricket_db_init_error}"}

    _maybe_track_views()

    # Phase 4 — adaptive scheduling. Event-driven by design (see
    # agents_cricket/adaptive_scheduler.py docstring), so this only ever
    # blocks to enforce the minimum gap between uploads once real data exists.
    upload_ok, upload_reason = should_upload_now_cricket()
    print(f"Adaptive scheduler: {upload_reason}")
    if not upload_ok:
        return {"status": "skipped_scheduler", "reason": upload_reason}

    posted = cricket_db.get_all_posted_match_ids()
    topics = get_all_topics(limit=8)
    print(f"Found {len(topics)} topics (news/live/upcoming/finished)")

    candidates = [t for t in topics if t["id"] not in posted]
    if not candidates:
        print("No new topics to post.")
        return {"status": "no_new_match"}

    # Phase 1.5 — saturation ranking. Prefers less-covered matches when
    # several finished matches are available; news/live/upcoming always
    # sort first since they're time-sensitive and have nothing to check yet.
    try:
        candidates = rank_topics_by_opportunity(candidates)
    except Exception as e:
        print(f"Saturation ranking skipped: {e}")
    new_match = candidates[0]

    uploads_today = _check_daily_cap()
    if uploads_today >= DAILY_UPLOAD_CAP:
        print(f"Daily cricket upload cap reached ({uploads_today}/{DAILY_UPLOAD_CAP}) — skipping.")
        return {"status": "daily_cap_reached", "uploads_today": uploads_today}

    topic_label = new_match.get("name") or new_match.get("title", "")
    print(f"Processing ({new_match.get('topic_type')}): {topic_label}")

    summary, structured = get_summary_for_topic(new_match)
    if not summary:
        print("Could not fetch summary — skipping this cycle.")
        return {"status": "summary_fetch_failed", "topic": topic_label}

    script = create_cricket_script(summary, standout_player=structured.get("standout_player"))
    print(f"Script ({len(script.split())} words): {script[:80]}...")

    # Phase 3 — A/B title testing. Falls back to seo_agent's own single-shot
    # title (via title_override=None) if this errors, so a title-test bug
    # never blocks the whole pipeline.
    winning_title = None
    try:
        ab_result = get_best_title_cricket(summary, script, teams=structured.get("teams"))
        winning_title = ab_result["winner"]["title"]
        print(f"AB-tested title winner ({ab_result['winner']['pattern']}, "
              f"score={ab_result['winner']['score']}): {winning_title}")
    except Exception as e:
        print(f"AB title test skipped: {e}")

    seo = generate_cricket_seo(summary, script, title_override=winning_title)
    print(f"Title: {seo['title']}")

    generate_voice(script, output_path="output/voice.mp3")
    create_srt(script, audio_path="output/voice.mp3")
    # # generative_image disconnected  # disconnected - use Pexels instead
    generate_backgrounds(summary, num_images=4, structured=structured)
    video_path = create_video()  # writes to output/final_video.mp4 per your existing agent

    video_id, video_url = upload_video(
        video_path, seo["title"], seo["description"], seo["hashtags"]
    )
    print(f"Uploaded: {video_url}")

    cricket_db.mark_posted(new_match["id"], new_match.get("name") or new_match.get("title", ""))
    cricket_db.upsert_video(
        video_id=video_id,
        title=seo["title"],
        published=datetime.now(timezone.utc).isoformat(),
        match_id=new_match["id"],
    )
    _increment_daily_cap()
    mark_upload_done_cricket()
    try:
        # Also mark on the shared English/Hindi scheduler in case any other
        # code path still checks it there — harmless no-op for cricket.
        from agents.adaptive_scheduler import mark_upload_done
        mark_upload_done("cricket")
    except Exception:
        pass

    return {"status": "uploaded", "video_url": video_url, "title": seo["title"]}


def run_comment_replies():
    """Optional: process + reply to cricket-channel comments. Not wired into
    the main cycle automatically (comment fetching costs YouTube API quota
    on every call) — call this from a separate, less-frequent trigger, e.g.
    a cron hitting a dedicated /trigger-comments endpoint a few times a day."""
    from agents_cricket.comment_reply_agent import process_comments_cricket
    return process_comments_cricket()


if __name__ == "__main__":
    result = run_cricket_cycle()
    print(result)
