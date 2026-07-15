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

from agents_cricket.database import db as cricket_db


def run_cricket_cycle():
    import traceback
    try:
        return _run_cricket_cycle_inner()
    except Exception as e:
        print(f"CRICKET PIPELINE CRASHED: {e}")
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


def _run_cricket_cycle_inner():
    from agents_cricket.trending_agent import get_finished_matches
    from agents_cricket.research_agent import get_match_summary
    from agents_cricket.script_agent import create_cricket_script
    from agents_cricket.seo_agent import generate_cricket_seo
    from agents_cricket.image_agent import generate_backgrounds
    from agents_cricket.upload_agent import upload_video
    from agents.voice_agent import generate_voice
    from agents.caption_agent import create_srt
    from agents_cricket.video_agent import create_video

    posted = cricket_db.get_all_posted_match_ids()
    matches = get_finished_matches(limit=5)
    print(f"Found {len(matches)} finished matches")

    new_match = next((m for m in matches if m["id"] not in posted), None)
    if not new_match:
        print("No new finished matches to post.")
        return {"status": "no_new_match"}

    print(f"Processing: {new_match['name']}")

    summary = get_match_summary(new_match)
    if not summary:
        print("Could not fetch scorecard — skipping this cycle.")
        return {"status": "scorecard_fetch_failed", "match": new_match["name"]}

    script = create_cricket_script(summary)
    print(f"Script ({len(script.split())} words): {script[:80]}...")

    seo = generate_cricket_seo(summary, script)
    print(f"Title: {seo['title']}")

    generate_voice(script, output_path="output/voice.mp3")
    create_srt(script, audio_path="output/voice.mp3")
    generate_backgrounds(summary, num_images=4)
    video_path = create_video()  # writes to output/final_video.mp4 per your existing agent

    video_id, video_url = upload_video(
        video_path, seo["title"], seo["description"], seo["hashtags"]
    )
    print(f"Uploaded: {video_url}")

    cricket_db.mark_posted(new_match["id"], new_match.get("name", ""))

    return {"status": "uploaded", "video_url": video_url, "title": seo["title"]}


if __name__ == "__main__":
    result = run_cricket_cycle()
    print(result)
