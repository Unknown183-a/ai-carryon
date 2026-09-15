# agents_gaming/view_tracker_agent.py
"""
View tracking for the Gaming channel — writes to agents_gaming.database
(Postgres/SQLite, gaming_-prefixed tables).

Called opportunistically from scheduler_gaming.py (throttled to
~once/hour), and can also be triggered manually from the dashboard's
Gaming Analytics tab.
"""

import datetime


def track_views_gaming(max_videos=20):
    """Fetch current stats for recent gaming videos and save a snapshot of
    each. Returns {video_id: video_dict} on success, {} on any failure
    (fails open — a tracking miss shouldn't break the pipeline)."""
    from agents_gaming.database import db, db_init_error

    if db is None:
        print(f"Gaming DB not available, skipping view tracking: {db_init_error}")
        return {}

    try:
        from agents_gaming.analytics_agent import get_recent_videos
        videos = get_recent_videos(max_videos)
    except Exception as e:
        print(f"Gaming view tracking error (YouTube API): {e}")
        return {}

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    history = {}

    for v in videos:
        vid = v["id"]
        try:
            existing = None
            for row in db.get_all_videos():
                if row["video_id"] == vid:
                    existing = row
                    break
            db.upsert_video(
                video_id=vid,
                title=v["title"],
                published=v.get("published", ""),
                clip_id=existing["clip_id"] if existing else None,
            )
            db.add_snapshot(
                video_id=vid,
                views=v["views"],
                likes=v["likes"],
                comments=v["comments"],
                timestamp=now,
            )
        except Exception as e:
            print(f"Gaming DB write error for {vid}: {e}")
        history[vid] = v

    print(f"✅ Tracked {len(videos)} gaming videos")
    return history


if __name__ == "__main__":
    h = track_views_gaming()
    print(f"Tracked {len(h)} gaming videos")
