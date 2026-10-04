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

# Gaming V2 (see AI_CarryON_Gaming_Pipeline_V2_Update.md). Set GAMING_V2_ENABLED=0
# to run the legacy flow (most-viewed clip -> single-prompt script) unchanged.
GAMING_V2_ENABLED = os.getenv("GAMING_V2_ENABLED", "1") != "0"
ANALYZE_TOP_K = int(os.getenv("GAMING_ANALYZE_TOP_K", "3"))     # clips downloaded + analysed per run
MAX_CLIP_TRIES = int(os.getenv("GAMING_MAX_CLIP_TRIES", "2"))   # clips whose scripts we try before giving up
REJECTED_KEY = "gaming_rejected_clips"
# Comma-separated Twitch language codes to prefer (empty = no preference).
CLIP_LANGUAGES = [l for l in os.getenv("GAMING_CLIP_LANGUAGES", "en").split(",") if l.strip()]

# moment type -> existing seo_agent title pattern (full SEO upgrade is V2 Phase 14)
SEO_PATTERN_BY_MOMENT = {
    "CLUTCH": "clutch", "INSANE_PLAY": "clutch",
    "FAIL": "funny", "FUNNY": "funny", "TROLL": "funny",
    "RECORD": "record",
    "REACTION": "reaction", "RAGE": "reaction", "LUCK": "reaction",
    "UNEXPECTED": "reaction", "DRAMA": "reaction",
}


def _load_rejected():
    import json
    try:
        raw = gaming_db.get_meta(REJECTED_KEY)
        return set(json.loads(raw)) if raw else set()
    except Exception:
        return set()


def _add_rejected(clip_id):
    """Remember clips whose scripts failed the quality bar so the next cycle
    moves on instead of re-picking the same clip forever (bounded to 50)."""
    import json
    try:
        ids = list(_load_rejected()) + [clip_id]
        gaming_db.set_meta(REJECTED_KEY, json.dumps(ids[-50:]))
    except Exception as e:
        print(f"Could not record rejected clip: {e}")


def _caption_text(script):
    """Script minus the '...' pause markers — TTS uses them for pauses, but
    they must not show up as caption words."""
    import re
    return re.sub(r"\.{2,}|\u2026", " ", script)


def _select_and_script_v2(candidates, posted):
    """V2 front half: score -> download+analyse top K -> re-score with real
    moment quality -> hook/commentary/quality loop on the best clips.
    Returns {"status": "ok", ...} or a terminal status dict for the scheduler."""
    import shutil
    from agents_gaming.trending_agent import FOLLOWED_STREAMERS
    from agents_gaming.clip_scorer import prefer_languages, rank_clips_v2
    from agents_gaming.moment_analyzer import analyze_moment
    from agents_gaming.video_clip_agent import download_twitch_clip
    from agents_gaming.research_agent import get_summary_for_clip
    from agents_gaming.script_agent import create_gaming_script_v2

    candidates = prefer_languages(candidates, CLIP_LANGUAGES, min_keep=ANALYZE_TOP_K)
    rejected = _load_rejected()
    shortlist = rank_clips_v2(candidates, posted, rejected, followed=FOLLOWED_STREAMERS, limit=ANALYZE_TOP_K)
    if not shortlist:
        print("All candidate clips already posted or rejected this cycle.")
        return {"status": "no_new_clip"}

    folder = "assets/gaming_clips"
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder, exist_ok=True)

    moments, paths = {}, {}
    for c in shortlist:
        try:
            paths[c["id"]] = download_twitch_clip(c, os.path.join(folder, f"{c['id']}.mp4"))
        except Exception as e:
            print(f"Clip {c.get('id')} download failed, skipping: {e}")
            continue
        moments[c["id"]] = analyze_moment(c, paths[c["id"]])
        m = moments[c["id"]]
        print(f"Analysed '{c.get('title')}': {m['moment_type']} intensity={m['intensity']} "
              f"[{m['source']}] (metadata score {c['_score']})")
        if m.get("is_gameplay") is False:
            # Category says "game" but the footage is IRL / webcam / lobby — not a gaming Short.
            print(f"Clip {c['id']} is not gameplay footage — skipping and remembering it")
            paths.pop(c["id"], None)
            moments.pop(c["id"], None)
            _add_rejected(c["id"])
    if not paths:
        return {"status": "no_new_clip", "reason": "no clip could be downloaded"}

    # Re-score against the FULL pool (percentiles stay meaningful), now with
    # real moment quality for the analysed clips; keep only clips we hold footage for.
    full = rank_clips_v2(candidates, posted, rejected, moments=moments, followed=FOLLOWED_STREAMERS)
    ranked = [c for c in full if c["id"] in paths]

    for clip in ranked[:MAX_CLIP_TRIES]:
        moment = moments[clip["id"]]
        print(f"Trying clip '{clip.get('title')}' by {clip.get('broadcaster_name')} "
              f"(V2 score {clip['_score']}, parts {clip['_score_parts']})")
        summary, structured = get_summary_for_clip(clip)
        structured["game"] = structured.get("game") or moment.get("game", "")
        result = create_gaming_script_v2(clip, moment, summary, structured, db=gaming_db)
        if result and result.get("unjudged"):
            # Reviewer outage, not a bad clip: don't burn the clip, don't try others.
            return {"status": "judge_unavailable"}
        if result and result["passed"]:
            return {"status": "ok", "clip": clip, "moment": moment, "summary": summary,
                    "structured": structured, "script": result["script"], "hook": result["hook"],
                    "clip_path": paths[clip["id"]]}
        print(f"Clip {clip.get('id')} rejected: script never cleared the quality bar")
        _add_rejected(clip["id"])

    return {"status": "quality_rejected"}


def run_gaming_cycle():
    import traceback
    try:
        return _run_gaming_cycle_inner()
    except Exception as e:
        print(f"GAMING PIPELINE CRASHED: {e}")
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


def _maybe_track_views():
    """Runs gaming view tracking at most once per hour, so every scheduler
    run doesn't burn YouTube API quota (same throttle pattern as cricket)."""
    from datetime import datetime, timezone
    VIEW_TRACK_INTERVAL_SECONDS = 55 * 60
    try:
        last = gaming_db.get_meta("last_view_track_at")
        if last:
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
            if elapsed < VIEW_TRACK_INTERVAL_SECONDS:
                return
        from agents_gaming.view_tracker_agent import track_views_gaming
        track_views_gaming()
        gaming_db.set_meta("last_view_track_at", datetime.now(timezone.utc).isoformat())
    except Exception as e:
        print(f"Gaming view tracking skipped: {e}")


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
    from agents_gaming.adaptive_scheduler import should_upload_now_gaming, mark_upload_done_gaming

    if gaming_db is None:
        return {"status": "error", "error": f"Gaming DB unavailable: {gaming_db_init_error}"}

    from agents.model_invoke_agent_english import reset_groq_budget
    reset_groq_budget()

    _maybe_track_views()

    upload_ok, upload_reason = should_upload_now_gaming()
    print(f"Adaptive scheduler: {upload_reason}")
    if not upload_ok:
        return {"status": "skipped_scheduler", "reason": upload_reason}

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

    moment, hook, clip_paths = None, None, None
    if GAMING_V2_ENABLED:
        sel = _select_and_script_v2(candidates, posted)
        if sel["status"] != "ok":
            return sel
        clip, moment, hook = sel["clip"], sel["moment"], sel["hook"]
        structured, script = sel["structured"], sel["script"]
        clip_paths = [sel["clip_path"]]
        print(f"Selected clip: '{clip.get('title')}' by {clip.get('broadcaster_name')} "
              f"-> {moment['moment_type']} (V2 score {clip['_score']})")
    else:
        clip = find_best_unposted_clip(candidates, posted)
        if not clip:
            print("All candidate clips already posted this cycle.")
            return {"status": "no_new_clip"}
        print(f"Selected clip: '{clip.get('title')}' by {clip.get('broadcaster_name')} "
              f"({clip.get('view_count', 0):,} views)")
        summary, structured = get_summary_for_clip(clip)
        script = create_gaming_script(summary, structured)

    print(f"Script ({len(script.split())} words): {script[:80]}...")

    seo_pattern = SEO_PATTERN_BY_MOMENT.get(moment["moment_type"]) if moment else None
    title, description, hashtags = generate_seo(structured, _caption_text(script), use_pattern=seo_pattern)
    print(f"Title: {title}")

    generate_voice(script, output_path="output/voice.mp3")
    create_srt(_caption_text(script), audio_path="output/voice.mp3")

    if clip_paths is None:
        print("Downloading Twitch clip footage...")
        clip_paths = get_gaming_background_clip(clip)

    # NOTE: the shared renderer currently drops the clip's own audio (-an) and
    # sizes the video to the voiceover. Preserving game audio is Gaming V2 Sprint 2.
    video_path = _create_video_from_pexels_clips(
        clip_paths, "output/voice.mp3", "output/captions.srt",
        music_path=None,
    )

    video_id, video_url = upload_video(video_path, title, description, hashtags)
    print(f"Uploaded: {video_url}")

    gaming_db.mark_posted(clip["id"], clip.get("title", ""), clip.get("broadcaster_name", ""))
    if GAMING_V2_ENABLED:
        from agents_gaming.script_agent import remember_script
        remember_script(gaming_db, script, (hook or {}).get("type"))
    gaming_db.upsert_video(
        video_id=video_id,
        title=title,
        published=datetime.now(timezone.utc).isoformat(),
        clip_id=clip["id"],
    )
    _increment_daily_cap()
    mark_upload_done_gaming()

    return {"status": "uploaded", "video_url": video_url, "title": title}


if __name__ == "__main__":
    result = run_gaming_cycle()
    print(result)
