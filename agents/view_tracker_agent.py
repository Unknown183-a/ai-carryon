# agents/view_tracker_agent.py
import os
import json
import datetime

HISTORY_FILE = "output/view_history.json"


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_history(history):
    os.makedirs("output", exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def track_views(max_videos=20):
    """
    Fetch current stats for recent videos and save to:
    1. SQLite database (primary — survives Render restarts)
    2. output/view_history.json (backup — same as before)
    """
    from agents.analytics_agent import get_recent_videos

    # Import database — fail gracefully if not available
    try:
        from agents.database import db
        use_db = True
    except Exception as e:
        print(f"DB not available, using JSON only: {e}")
        use_db = False

    videos = get_recent_videos(max_videos)
    history = load_history()
    now = datetime.datetime.now(datetime.UTC).isoformat()

    for v in videos:
        vid = v["id"]

        # ── Write to SQLite ────────────────────────────────────────────
        if use_db:
            try:
                db.upsert_video(
                    video_id=vid,
                    title=v["title"],
                    published=v.get("published", ""),
                    channel="english",
                )
                db.add_snapshot(
                    video_id=vid,
                    views=v["views"],
                    likes=v["likes"],
                    comments=v["comments"],
                    timestamp=now,
                )
            except Exception as e:
                print(f"DB write error for {vid}: {e}")

        # ── Write to JSON (backup) ─────────────────────────────────────
        if vid not in history:
            history[vid] = {
                "title": v["title"],
                "published": v.get("published", ""),
                "url": v.get("url", ""),
                "snapshots": []
            }

        history[vid]["title"] = v["title"]
        history[vid]["url"] = v.get("url", history[vid].get("url", ""))
        history[vid]["snapshots"].append({
            "timestamp": now,
            "views": v["views"],
            "likes": v["likes"],
            "comments": v["comments"],
        })

    save_history(history)

    if use_db:
        snapshot_count = sum(
            len(db.get_snapshots(v["id"])) for v in videos
        )
        print(f"✅ Tracked {len(videos)} videos — {snapshot_count} total snapshots in DB")

    return history


if __name__ == "__main__":
    h = track_views()
    print(f"Tracked {len(h)} videos at {datetime.datetime.now(datetime.UTC).isoformat()}")
