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

POSTED_PATH = "output/cricket_posted.json"


def _load_posted():
    if os.path.exists(POSTED_PATH):
        with open(POSTED_PATH) as f:
            return set(json.load(f))
    return set()


def _save_posted(posted_ids):
    os.makedirs("output", exist_ok=True)
    with open(POSTED_PATH, "w") as f:
        json.dump(list(posted_ids), f)


def run_cricket_cycle():
    from agents_cricket.trending_agent import get_finished_matches
    from agents_cricket.research_agent import get_match_summary
    from agents_cricket.script_agent import create_cricket_script
    from agents_cricket.seo_agent import generate_cricket_seo
    from agents_cricket.image_agent import generate_backgrounds
    from agents_cricket.upload_agent import upload_video
    from agents.voice_agent import generate_voice
    from agents.caption_agent import create_srt
    from agents.video_agent import create_video

    posted = _load_posted()
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

    posted.add(new_match["id"])
    _save_posted(posted)

    return {"status": "uploaded", "video_url": video_url, "title": seo["title"]}


if __name__ == "__main__":
    result = run_cricket_cycle()
    print(result)
