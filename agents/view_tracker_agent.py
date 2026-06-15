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
    Fetch current stats for recent videos and append a timestamped
    snapshot to output/view_history.json.

    Structure:
    {
      "<video_id>": {
        "title": "...",
        "published": "2026-06-14T...",
        "snapshots": [
          {"timestamp": "2026-06-15T12:00:00", "views": 489, "likes": 7, "comments": 0},
          ...
        ]
      },
      ...
    }
    """
    from agents.analytics_agent import get_recent_videos

    videos = get_recent_videos(max_videos)
    history = load_history()

    now = datetime.datetime.now(datetime.UTC).isoformat()

    for v in videos:
        vid = v["id"]
        if vid not in history:
            history[vid] = {
                "title": v["title"],
                "published": v.get("published", ""),
                "url": v.get("url", ""),
                "snapshots": []
            }

        # Keep title/url updated in case it changed
        history[vid]["title"] = v["title"]
        history[vid]["url"] = v.get("url", history[vid].get("url", ""))

        history[vid]["snapshots"].append({
            "timestamp": now,
            "views": v["views"],
            "likes": v["likes"],
            "comments": v["comments"]
        })

    save_history(history)
    return history


if __name__ == "__main__":
    h = track_views()
    print(f"Tracked {len(h)} videos at {datetime.datetime.now(datetime.UTC).isoformat()}")
