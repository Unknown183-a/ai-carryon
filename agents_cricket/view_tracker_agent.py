# agents_cricket/view_tracker_agent.py
"""
View tracking for the Cricket channel — writes to Supabase Postgres
(agents_cricket.database) instead of the shared SQLite used by
English/Hindi, since cricket runs on Render's free tier with no disk.

Called opportunistically from scheduler_cricket.py's run_cricket_cycle()
(throttled to ~once/hour), and can also be triggered manually from the
dashboard's Cricket Analytics tab.
"""

import datetime


def track_views_cricket(max_videos=20):
    """Fetch current stats for recent cricket videos and save a snapshot
    of each to Postgres. Returns {video_id: video_dict} on success, {} on
    any failure (fails open — a tracking miss shouldn't break the pipeline)."""
    from agents_cricket.database import db, db_init_error

    if db is None:
        print(f"Cricket DB not available, skipping view tracking: {db_init_error}")
        return {}

    try:
        from agents_cricket.analytics_agent import get_recent_videos
        videos = get_recent_videos(max_videos)
    except Exception as e:
        print(f"Cricket view tracking error (YouTube API): {e}")
        return {}

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    history = {}

    for v in videos:
        vid = v["id"]
        try:
            # Preserve match_id already stored by scheduler_cricket.py's upsert
            # at upload time — only update title/published here.
            existing = None
            for row in db.get_all_videos():
                if row["video_id"] == vid:
                    existing = row
                    break
            db.upsert_video(
                video_id=vid,
                title=v["title"],
                published=v.get("published", ""),
                match_id=existing["match_id"] if existing else None,
            )
            db.add_snapshot(
                video_id=vid,
                views=v["views"],
                likes=v["likes"],
                comments=v["comments"],
                timestamp=now,
            )
        except Exception as e:
            print(f"Cricket DB write error for {vid}: {e}")
        history[vid] = v

    print(f"✅ Tracked {len(videos)} cricket videos")
    return history


if __name__ == "__main__":
    h = track_views_cricket()
    print(f"Tracked {len(h)} cricket videos")
