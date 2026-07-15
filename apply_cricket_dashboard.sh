#!/bin/bash
set -e

mkdir -p $(dirname agents_cricket/database.py)
cat > agents_cricket/database.py << 'CRICKETEOF'
"""
agents_cricket/database.py — Postgres (Supabase) database for the Cricket channel.

Mirrors agents/database.py's schema and API, but:
  - Uses Postgres (psycopg2) instead of SQLite, since Render's free tier
    has no persistent disk — Supabase gives us a persistent DB over the network.
  - channel is hardcoded to "cricket" everywhere.
  - Table names are prefixed cricket_ to keep this fully isolated from
    anything else that might land in the same Supabase project later.

Usage:
    from agents_cricket.database import db
    db.mark_posted(match_id)
    already_posted = db.get_recent_posted(hours=24*365)  # cricket has no daily cap, check all-time
"""

import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "")


class CricketDatabase:
    def __init__(self, database_url=None):
        self.database_url = database_url or DATABASE_URL
        if not self.database_url:
            raise RuntimeError("DATABASE_URL not set — cannot connect to Supabase Postgres")
        self._init_tables()

    @contextmanager
    def _conn(self):
        conn = psycopg2.connect(self.database_url, cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_tables(self):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS cricket_videos (
                        video_id    TEXT PRIMARY KEY,
                        title       TEXT,
                        published   TEXT,
                        match_id    TEXT,
                        created_at  TIMESTAMPTZ DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS cricket_snapshots (
                        id          SERIAL PRIMARY KEY,
                        video_id    TEXT NOT NULL REFERENCES cricket_videos(video_id),
                        views       INTEGER DEFAULT 0,
                        likes       INTEGER DEFAULT 0,
                        comments    INTEGER DEFAULT 0,
                        timestamp   TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS cricket_posted_matches (
                        id          SERIAL PRIMARY KEY,
                        match_id    TEXT NOT NULL UNIQUE,
                        match_name  TEXT,
                        posted_at   TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS cricket_meta (
                        key         TEXT PRIMARY KEY,
                        value       TEXT
                    );

                    CREATE INDEX IF NOT EXISTS idx_cricket_snapshots_video_id
                        ON cricket_snapshots(video_id);
                """)

    # ── Videos ────────────────────────────────────────────────────────────

    def upsert_video(self, video_id, title, published, match_id=None):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO cricket_videos (video_id, title, published, match_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (video_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        published = EXCLUDED.published
                """, (video_id, title, published, match_id))

    def get_all_videos(self):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM cricket_videos ORDER BY created_at DESC")
                return [dict(r) for r in cur.fetchall()]

    # ── Snapshots ────────────────────────────────────────────────────────

    def add_snapshot(self, video_id, views, likes=0, comments=0, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO cricket_snapshots (video_id, views, likes, comments, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                """, (video_id, views, likes, comments, timestamp))

    def get_snapshots(self, video_id):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM cricket_snapshots
                    WHERE video_id = %s ORDER BY timestamp ASC
                """, (video_id,))
                return [dict(r) for r in cur.fetchall()]

    def get_all_snapshots(self):
        """Return all snapshots grouped by video_id — same shape as
        agents/database.py's get_all_snapshots(), so agents_cricket.velocity_agent
        can reuse the exact same velocity-computation logic as English/Hindi."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM cricket_videos")
                videos = cur.fetchall()
                result = {}
                for video in videos:
                    vid_id = video["video_id"]
                    cur.execute("""
                        SELECT views, likes, comments, timestamp
                        FROM cricket_snapshots WHERE video_id = %s
                        ORDER BY timestamp ASC
                    """, (vid_id,))
                    snaps = [dict(r) for r in cur.fetchall()]
                    result[vid_id] = {
                        "title": video["title"],
                        "published": video["published"],
                        "match_id": video["match_id"],
                        "snapshots": snaps,
                    }
                return result

    # ── Meta (key/value, used to throttle YouTube API calls) ──────────────

    def get_meta(self, key):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM cricket_meta WHERE key = %s", (key,))
                row = cur.fetchone()
                return row["value"] if row else None

    def set_meta(self, key, value):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO cricket_meta (key, value) VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """, (key, value))

    # ── Posted Matches (replaces cricket_posted.json) ──────────────────────

    def mark_posted(self, match_id, match_name="", posted_at=None):
        if posted_at is None:
            posted_at = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO cricket_posted_matches (match_id, match_name, posted_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (match_id) DO NOTHING
                """, (match_id, match_name, posted_at))

    def is_posted(self, match_id):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM cricket_posted_matches WHERE match_id = %s",
                    (match_id,)
                )
                return cur.fetchone() is not None

    def get_all_posted_match_ids(self):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT match_id FROM cricket_posted_matches")
                return {r["match_id"] for r in cur.fetchall()}


# Singleton instance — same pattern as agents/database.py's `db`.
# Wrapped in try/except: the Render worker always has DATABASE_URL set, but
# the Railway dashboard is a separate environment and may not (yet). Callers
# (velocity_agent, dashboard pages) check `db_init_error` and show a helpful
# message rather than the whole page crashing on import.
db_init_error = None
try:
    db = CricketDatabase()
except Exception as e:
    db = None
    db_init_error = str(e)
CRICKETEOF
echo 'Wrote agents_cricket/database.py'

mkdir -p $(dirname agents_cricket/upload_agent.py)
cat > agents_cricket/upload_agent.py << 'CRICKETEOF'
# agents_cricket/upload_agent.py
import os
import pickle
import base64
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Broader scopes needed for view tracking (read channel stats, playlists, videos).
# If the cricket token was only ever authorized with youtube.upload, readonly
# calls will fail with insufficient_scope — in that case the token needs to be
# regenerated once locally with both scopes and re-pickled/base64'd into
# CRICKET_YOUTUBE_TOKEN_B64. track_views_cricket() handles that failure gracefully.
SCOPES_READ = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def get_youtube_client_readonly():
    """Read-capable client for view tracking (channels, playlists, videos.list).
    Reuses the same pickled cricket credentials as upload — see SCOPES_READ note above."""
    return authenticate_youtube()


def authenticate_youtube():
    creds = None
    token_b64 = os.getenv("CRICKET_YOUTUBE_TOKEN_B64")
    if token_b64:
        creds = pickle.loads(base64.b64decode(token_b64))
    elif os.path.exists("cricket_token.pickle"):
        with open("cricket_token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds:
        raise RuntimeError(
            "No cricket YouTube token found. Generate one locally with the "
            "cricket channel's Google account, pickle it, base64-encode it, "
            "and set CRICKET_YOUTUBE_TOKEN_B64 on Render."
        )
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return build("youtube", "v3", credentials=creds)


def upload_video(video_path, title, description, hashtags, thumbnail_path=None):
    youtube = authenticate_youtube()

    hashtag_str = " ".join(hashtags) if isinstance(hashtags, list) else hashtags
    tags = [h.strip("#") for h in (hashtags if isinstance(hashtags, list) else hashtags.split())]

    full_description = f"""{description}

━━━━━━━━━━━━━━━━━━━━━━━━
🏏 Subscribe for daily cricket recaps!
━━━━━━━━━━━━━━━━━━━━━━━━

{hashtag_str} #Shorts #Cricket"""

    body = {
        "snippet": {
            "title": title,
            "description": full_description,
            "tags": tags + ["Shorts", "Cricket", "IPL"],
            "categoryId": "17",  # Sports
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=1024 * 1024 * 5)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumbnail_path)).execute()
        except Exception as e:
            print(f"Thumbnail upload failed: {e}")

    return video_id, f"https://www.youtube.com/watch?v={video_id}"
CRICKETEOF
echo 'Wrote agents_cricket/upload_agent.py'

mkdir -p $(dirname agents_cricket/analytics_agent.py)
cat > agents_cricket/analytics_agent.py << 'CRICKETEOF'
# agents_cricket/analytics_agent.py
"""
Analytics for the Cricket channel — same interface as agents/analytics_agent.py
(get_channel_stats, get_recent_videos) but authenticated as the cricket
channel via agents_cricket.upload_agent's pickled credentials, since cricket
runs on a separate Google account/channel from English and Hindi.
"""


def get_channel_stats():
    from agents_cricket.upload_agent import get_youtube_client_readonly

    youtube = get_youtube_client_readonly()
    response = youtube.channels().list(part="statistics,snippet", mine=True).execute()
    channel = response["items"][0]
    return {
        "name": channel["snippet"]["title"],
        "subscribers": int(channel["statistics"].get("subscriberCount", 0)),
        "total_views": int(channel["statistics"].get("viewCount", 0)),
        "video_count": int(channel["statistics"].get("videoCount", 0)),
    }


def get_recent_videos(max_results=20):
    from agents_cricket.upload_agent import get_youtube_client_readonly

    youtube = get_youtube_client_readonly()

    channel = youtube.channels().list(part="contentDetails", mine=True).execute()
    uploads_playlist = channel["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    playlist_response = youtube.playlistItems().list(
        part="snippet",
        playlistId=uploads_playlist,
        maxResults=max_results,
    ).execute()

    video_ids = [item["snippet"]["resourceId"]["videoId"] for item in playlist_response.get("items", [])]
    if not video_ids:
        return []

    videos_response = youtube.videos().list(
        part="statistics,snippet",
        id=",".join(video_ids),
    ).execute()

    videos = []
    for item in videos_response["items"]:
        stats = item["statistics"]
        videos.append({
            "id": item["id"],
            "title": item["snippet"]["title"],
            "published": item["snippet"]["publishedAt"][:10],
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "url": f"https://youtube.com/watch?v={item['id']}",
        })

    return sorted(videos, key=lambda x: x["views"], reverse=True)
CRICKETEOF
echo 'Wrote agents_cricket/analytics_agent.py'

mkdir -p $(dirname agents_cricket/view_tracker_agent.py)
cat > agents_cricket/view_tracker_agent.py << 'CRICKETEOF'
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
CRICKETEOF
echo 'Wrote agents_cricket/view_tracker_agent.py'

mkdir -p $(dirname agents_cricket/velocity_agent.py)
cat > agents_cricket/velocity_agent.py << 'CRICKETEOF'
# agents_cricket/velocity_agent.py
"""
Phase 1 velocity analysis for the Cricket channel — same math as
agents/velocity_agent.py and agents_hindi/velocity_agent.py, but sources
data from Supabase Postgres (agents_cricket.database) instead of SQLite,
since cricket runs on Render's free tier with no persistent disk.

Exposes the same function names/shapes as the Hindi module so
pages/peak_hours.py and pages/schedule.py can add cricket as a third
option with minimal branching.
"""

from datetime import datetime, timezone
from collections import defaultdict


def _parse_ts(ts_str: str) -> datetime:
    ts_str = ts_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def compute_velocity_cricket():
    """Compute per-video velocity for the cricket channel.
    Returns {"error": "..."} if the cricket DB isn't reachable in this environment."""
    from agents_cricket.database import db, db_init_error

    if db is None:
        return {"error": f"Cricket DB unavailable: {db_init_error}"}

    try:
        all_data = db.get_all_snapshots()
    except Exception as e:
        return {"error": f"Cricket DB query failed: {e}"}

    result = {}
    for video_id, data in all_data.items():
        snapshots = data.get("snapshots", [])
        if len(snapshots) < 2:
            continue

        velocity_points = []
        for i in range(1, len(snapshots)):
            prev, curr = snapshots[i - 1], snapshots[i]
            try:
                t_prev = _parse_ts(prev["timestamp"])
                t_curr = _parse_ts(curr["timestamp"])
            except (KeyError, ValueError):
                continue

            hours_elapsed = (t_curr - t_prev).total_seconds() / 3600
            if hours_elapsed <= 0:
                continue

            views_gained = max(curr.get("views", 0) - prev.get("views", 0), 0)
            velocity = views_gained / hours_elapsed

            velocity_points.append({
                "timestamp": curr["timestamp"],
                "hour_of_day": t_curr.hour,
                "views": curr.get("views", 0),
                "views_gained": views_gained,
                "hours_elapsed": round(hours_elapsed, 4),
                "velocity": round(velocity, 4),
            })

        if not velocity_points:
            continue

        velocities = [p["velocity"] for p in velocity_points]
        result[video_id] = {
            "title": data.get("title", ""),
            "published": data.get("published", ""),
            "velocity_points": velocity_points,
            "avg_velocity": round(sum(velocities) / len(velocities), 4),
            "peak_velocity": round(max(velocities), 4),
            "total_snapshots": len(snapshots),
        }

    return result


def get_peak_hours_cricket():
    velocity_data = compute_velocity_cricket()
    if "error" in velocity_data:
        return velocity_data

    hour_buckets = defaultdict(list)
    for video_data in velocity_data.values():
        for point in video_data["velocity_points"]:
            hour_buckets[point["hour_of_day"]].append(point["velocity"])

    peak_hours = {}
    for hour in range(24):
        values = hour_buckets.get(hour, [])
        peak_hours[hour] = {
            "avg_velocity": round(sum(values) / len(values), 4) if values else 0.0,
            "sample_count": len(values),
        }
    return peak_hours


def get_best_upload_windows_cricket(top_n=5):
    peak_hours = get_peak_hours_cricket()
    if isinstance(peak_hours, dict) and "error" in peak_hours:
        return []
    ranked = sorted(
        [{"hour": h, **stats} for h, stats in peak_hours.items() if stats["sample_count"] > 0],
        key=lambda x: x["avg_velocity"],
        reverse=True,
    )
    return ranked[:top_n]


def get_best_upload_hour_cricket():
    windows = get_best_upload_windows_cricket(top_n=1)
    if windows and windows[0]["sample_count"] >= 3:
        return windows[0]["hour"]
    return None


def get_video_velocity_summary_cricket():
    velocity_data = compute_velocity_cricket()
    if "error" in velocity_data:
        return []
    summary = [
        {
            "video_id": vid,
            "title": data["title"],
            "published": data["published"],
            "avg_velocity": data["avg_velocity"],
            "peak_velocity": data["peak_velocity"],
            "total_snapshots": data["total_snapshots"],
        }
        for vid, data in velocity_data.items()
    ]
    return sorted(summary, key=lambda x: x["avg_velocity"], reverse=True)


def load_and_analyse_cricket():
    velocity_data = compute_velocity_cricket()
    if "error" in velocity_data:
        return {"error": velocity_data["error"]}

    peak_hours = get_peak_hours_cricket()
    best_windows = get_best_upload_windows_cricket(top_n=5)
    video_summary = get_video_velocity_summary_cricket()
    total_points = sum(len(v["velocity_points"]) for v in velocity_data.values())

    return {
        "velocity_data": velocity_data,
        "peak_hours": peak_hours,
        "best_upload_windows": best_windows,
        "video_summary": video_summary,
        "total_videos_analysed": len(velocity_data),
        "total_velocity_points": total_points,
    }


if __name__ == "__main__":
    analysis = load_and_analyse_cricket()
    if "error" in analysis:
        print(f"Error: {analysis['error']}")
    else:
        print(f"Cricket videos analysed: {analysis['total_videos_analysed']}")
        print(f"Cricket data points: {analysis['total_velocity_points']}")
        print("\nBest cricket upload windows:")
        for w in analysis["best_upload_windows"]:
            print(f"  {w['hour']:02d}:00 UTC — {w['avg_velocity']:.1f} views/hr ({w['sample_count']} samples)")
CRICKETEOF
echo 'Wrote agents_cricket/velocity_agent.py'

mkdir -p $(dirname scheduler_cricket.py)
cat > scheduler_cricket.py << 'CRICKETEOF'
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
    from datetime import datetime, timezone

    if cricket_db is None:
        return {"status": "error", "error": f"Cricket DB unavailable: {cricket_db_init_error}"}

    _maybe_track_views()

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
    cricket_db.upsert_video(
        video_id=video_id,
        title=seo["title"],
        published=datetime.now(timezone.utc).isoformat(),
        match_id=new_match["id"],
    )

    return {"status": "uploaded", "video_url": video_url, "title": seo["title"]}


if __name__ == "__main__":
    result = run_cricket_cycle()
    print(result)
CRICKETEOF
echo 'Wrote scheduler_cricket.py'

mkdir -p $(dirname pages/peak_hours.py)
cat > pages/peak_hours.py << 'CRICKETEOF'
"""
pages/peak_hours.py — Phase 1 Dashboard: Velocity Analysis & Peak Upload Windows
Reads from SQLite (primary) — works for both English and Hindi channels.
"""

import sys
import os

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

st.set_page_config(page_title="Peak Hours · AI CarryON", page_icon="⚡", layout="wide")

from agents.dashboard_sync import sync_all_channel_data
_sync_status = sync_all_channel_data()

APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
if APP_PASSWORD:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if pwd == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Wrong password")
        st.stop()

st.title("⚡ Peak Hours")
st.caption("View velocity analysis — when your channel gets the most traction.")

# ── Channel selector ────────────────────────────────────────────────────────

channel = st.radio("Channel", ["AI CarryON (English)", "Hindi AI CarryON", "Cricket AI CarryON"], horizontal=True)
is_hindi = channel == "Hindi AI CarryON"
is_cricket = channel == "Cricket AI CarryON"

col_refresh, _ = st.columns([1, 5])
with col_refresh:
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

# ── Load analysis from SQLite / Postgres ────────────────────────────────────

@st.cache_data(ttl=300)
def load_analysis(hindi: bool, cricket: bool):
    try:
        if cricket:
            from agents_cricket.velocity_agent import load_and_analyse_cricket
            return load_and_analyse_cricket()
        elif hindi:
            from agents_hindi.velocity_agent import load_and_analyse_hindi
            return load_and_analyse_hindi()
        else:
            from agents.velocity_agent import load_and_analyse
            return load_and_analyse("output/view_history.json")
    except Exception as e:
        return {"error": str(e)}

with st.spinner("Loading velocity data…"):
    analysis = load_analysis(is_hindi, is_cricket)

if "error" in analysis:
    st.error(f"Could not load data: {analysis['error']}")
    st.stop()

if analysis["total_velocity_points"] < 10:
    st.warning(
        f"Only {analysis['total_velocity_points']} data points so far for {channel}. "
        "Need more hourly snapshots. Come back in a day or two."
    )

peak_hours    = analysis["peak_hours"]
best_windows  = analysis["best_upload_windows"]
video_summary = analysis.get("video_summary", [])

# Build video_summary from velocity_data if not present (Hindi path)
if not video_summary and "velocity_data" in analysis:
    video_summary = sorted([
        {
            "video_id": vid,
            "title": v["title"],
            "published": v["published"],
            "avg_velocity": v["avg_velocity"],
            "peak_velocity": v["peak_velocity"],
            "total_snapshots": v["total_snapshots"],
        }
        for vid, v in analysis["velocity_data"].items()
    ], key=lambda x: x["avg_velocity"], reverse=True)

best_hour     = best_windows[0]["hour"]     if best_windows else None
best_velocity = best_windows[0]["avg_velocity"] if best_windows else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Videos analysed",    analysis["total_videos_analysed"])
col2.metric("Velocity data points", analysis["total_velocity_points"])
col3.metric("Best upload hour (UTC)", f"{best_hour:02d}:00" if best_hour is not None else "—")
col4.metric("Peak avg velocity",  f"{best_velocity:.1f} v/hr")

st.divider()

# ── 24h bar chart ──────────────────────────────────────────────────────────

st.subheader(f"Average view velocity by hour of day (UTC) — {channel}")

hours         = list(range(24))
avg_velocities = [peak_hours[h]["avg_velocity"] for h in hours]
sample_counts  = [peak_hours[h]["sample_count"]  for h in hours]
hour_labels    = [f"{h:02d}:00" for h in hours]
top_hour_set   = {w["hour"] for w in best_windows}
bar_colors     = ["#6366f1" if h in top_hour_set else "#334155" for h in hours]

fig_peak = go.Figure(go.Bar(
    x=hour_labels, y=avg_velocities,
    marker_color=bar_colors,
    hovertemplate="<b>%{x}</b><br>Avg velocity: %{y:.1f} views/hr<br>Samples: %{customdata}<extra></extra>",
    customdata=sample_counts,
))
fig_peak.update_layout(
    xaxis_title="Hour of day (UTC)", yaxis_title="Avg views per hour",
    plot_bgcolor="#0f172a", paper_bgcolor="#0f172a", font_color="#e2e8f0",
    margin=dict(t=20, b=40, l=50, r=20), height=340, showlegend=False,
)
for w in best_windows:
    fig_peak.add_vrect(x0=w["hour"]-0.5, x1=w["hour"]+0.5,
                       fillcolor="rgba(99,102,241,0.12)", line_width=0)

st.plotly_chart(fig_peak, use_container_width=True)

# ── Best windows table ─────────────────────────────────────────────────────

st.subheader("🏆 Top 5 upload windows")
if best_windows:
    df_w = pd.DataFrame(best_windows)
    df_w["hour_label"]    = df_w["hour"].apply(lambda h: f"{h:02d}:00 UTC")
    df_w["avg_velocity"]  = df_w["avg_velocity"].apply(lambda v: f"{v:.1f} v/hr")
    df_w["sample_count"]  = df_w["sample_count"].apply(lambda n: f"{n} snapshots")
    df_w = df_w[["hour_label", "avg_velocity", "sample_count"]]
    df_w.columns = ["Upload hour (UTC)", "Avg velocity", "Data points"]
    df_w.index = ["🥇","🥈","🥉","4th","5th"][:len(df_w)]
    st.dataframe(df_w, use_container_width=True)
else:
    st.info("No upload windows yet — need more snapshot data.")

st.divider()

# ── Per-video sparkline ────────────────────────────────────────────────────

st.subheader("Video velocity over time")
velocity_data = analysis.get("velocity_data", {})

if velocity_data:
    video_options = {
        (v["title"][:55] + "…" if len(v["title"]) > 55 else v["title"]): vid_id
        for vid_id, v in velocity_data.items()
    }
    selected_title = st.selectbox("Select a video", list(video_options.keys()))
    selected_id    = video_options[selected_title]
    vdata          = velocity_data[selected_id]

    df_v = pd.DataFrame(vdata["velocity_points"])
    df_v["timestamp"] = pd.to_datetime(df_v["timestamp"])

    col_a, col_b = st.columns([2, 1])
    with col_a:
        fig_v = px.area(df_v, x="timestamp", y="velocity",
                        labels={"velocity": "Views / hr", "timestamp": ""},
                        color_discrete_sequence=["#6366f1"])
        fig_v.update_layout(plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
                            font_color="#e2e8f0",
                            margin=dict(t=10, b=30, l=50, r=20), height=260)
        fig_v.update_traces(fillcolor="rgba(99,102,241,0.15)", line_width=2)
        st.plotly_chart(fig_v, use_container_width=True)
    with col_b:
        st.metric("Avg velocity",  f"{vdata['avg_velocity']:.1f} v/hr")
        st.metric("Peak velocity", f"{vdata['peak_velocity']:.1f} v/hr")
        st.metric("Snapshots",     vdata["total_snapshots"])
        if vdata["published"]:
            st.caption(f"Published: {vdata['published']}")
else:
    st.info("No video velocity data yet.")

st.divider()

# ── Full ranking table ─────────────────────────────────────────────────────

st.subheader("All videos — velocity ranking")
if video_summary:
    df_rank = pd.DataFrame(video_summary)
    df_rank["avg_velocity"]  = df_rank["avg_velocity"].apply(lambda v: f"{v:.1f}")
    df_rank["peak_velocity"] = df_rank["peak_velocity"].apply(lambda v: f"{v:.1f}")
    df_rank = df_rank[["title","published","avg_velocity","peak_velocity","total_snapshots"]]
    df_rank.columns = ["Title","Published","Avg v/hr","Peak v/hr","Snapshots"]
    df_rank.index = range(1, len(df_rank)+1)
    st.dataframe(df_rank, use_container_width=True)
else:
    st.info("No ranked videos yet.")

st.caption(
    f"Channel: {channel} · Data refreshes every 5 min · Loaded from SQLite · "
    f"Last computed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
)
CRICKETEOF
echo 'Wrote pages/peak_hours.py'

mkdir -p $(dirname pages/schedule.py)
cat > pages/schedule.py << 'CRICKETEOF'
"""
pages/schedule.py — Phase 4 Dashboard: Adaptive Scheduling
Shows optimal upload windows and current schedule recommendation.
Works for both English and Hindi channels via selector.
"""

import sys
import os
from datetime import datetime, timezone

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

st.set_page_config(page_title="Schedule · AI CarryON", page_icon="🕐", layout="wide")

from agents.dashboard_sync import sync_all_channel_data
_sync_status = sync_all_channel_data()


APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
if APP_PASSWORD:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if pwd == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Wrong password")
        st.stop()

st.title("🕐 Adaptive Schedule")
st.caption("Upload at the exact hour your audience is most active.")

# ── Channel selector ────────────────────────────────────────────────────────

channel = st.radio("Channel", ["AI CarryON (English)", "Hindi AI CarryON", "Cricket AI CarryON"], horizontal=True)
is_hindi = channel == "Hindi AI CarryON"
is_cricket = channel == "Cricket AI CarryON"

col_refresh, _ = st.columns([1, 5])
with col_refresh:
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

# ── Load data ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_recommendation(hindi: bool, cricket: bool):
    try:
        if cricket:
            from agents_cricket.velocity_agent import load_and_analyse_cricket, get_best_upload_hour_cricket
            analysis = load_and_analyse_cricket()
            if "error" in analysis:
                return {"error": analysis["error"]}
            best_hour = get_best_upload_hour_cricket()
            windows = analysis["best_upload_windows"]
            peak_hours = analysis["peak_hours"]
            total_points = analysis["total_velocity_points"]
            source = "Cricket Postgres (Supabase)"
        elif hindi:
            from agents_hindi.velocity_agent import load_and_analyse_hindi, get_best_upload_hour_hindi
            analysis = load_and_analyse_hindi()
            best_hour = get_best_upload_hour_hindi()
            windows = analysis["best_upload_windows"]
            peak_hours = analysis["peak_hours"]
            total_points = analysis["total_velocity_points"]
            source = "Hindi SQLite"
        else:
            from agents.adaptive_scheduler import get_schedule_recommendation, get_best_upload_windows, get_peak_hours_analysis
            rec = get_schedule_recommendation()
            windows, _ = get_best_upload_windows(top_n=24)
            peak_hours, source = get_peak_hours_analysis()
            best_hour = rec.get("best_hour")
            total_points = None

        return {
            "best_hour": best_hour,
            "windows": windows,
            "peak_hours": peak_hours,
            "source": source,
            "total_points": total_points,
        }
    except Exception as e:
        return {"error": str(e)}

with st.spinner("Analyzing view velocity data..."):
    data = load_recommendation(is_hindi, is_cricket)

if "error" in data:
    st.error(f"Error: {data['error']}")
    st.stop()

best_hour = data["best_hour"]
top_windows = data["windows"]
peak_hours = data["peak_hours"]
source = data["source"]

if best_hour is None:
    st.warning("⏳ Not enough data yet for this channel. Need more hourly snapshots.")
else:
    st.success(f"✅ Best upload hour identified: {best_hour:02d}:00 UTC")

# ── Top metrics ────────────────────────────────────────────────────────────

now_utc = datetime.now(timezone.utc)
ist_hour = (best_hour + 5) % 24 if best_hour is not None else None

col1, col2, col3, col4 = st.columns(4)
col1.metric("Best upload hour (UTC)", f"{best_hour:02d}:00" if best_hour is not None else "—")
col2.metric("Best upload hour (IST)", f"{ist_hour:02d}:30" if ist_hour is not None else "—")
col3.metric("Current UTC time", now_utc.strftime("%H:%M"))
col4.metric(
    "Recommendation",
    "Upload now ✅" if best_hour == now_utc.hour else
    f"Wait for {best_hour:02d}:00 UTC" if best_hour is not None else "—"
)

st.divider()

# ── 24h velocity chart ─────────────────────────────────────────────────────

_channel_label = "Cricket" if is_cricket else ("Hindi" if is_hindi else "English")
st.subheader(f"📈 {_channel_label} view velocity by hour (UTC)")

try:
    hours = list(range(24))
    velocities = [peak_hours.get(h, {}).get("avg_velocity", 0) for h in hours]
    samples = [peak_hours.get(h, {}).get("sample_count", 0) for h in hours]
    labels = [f"{h:02d}:00" for h in hours]
    top_set = {w["hour"] for w in top_windows[:3]} if top_windows else set()
    colors = ["#6366f1" if h in top_set else "#334155" for h in hours]

    fig = go.Figure(go.Bar(
        x=labels,
        y=velocities,
        marker_color=colors,
        hovertemplate="<b>%{x} UTC</b><br>Avg velocity: %{y:.1f} views/hr<br>Samples: %{customdata}<extra></extra>",
        customdata=samples,
    ))

    now_label = now_utc.strftime("%H:00")
    if now_label in labels:
        now_idx = labels.index(now_label)
        fig.add_vrect(
            x0=now_idx - 0.5,
            x1=now_idx + 0.5,
            fillcolor="rgba(245,158,11,0.15)",
            line_color="#f59e0b",
            line_width=2,
            annotation_text="Now",
            annotation_position="top",
        )

    fig.update_layout(
        plot_bgcolor="#0f172a",
        paper_bgcolor="#0f172a",
        font_color="#e2e8f0",
        margin=dict(t=20, b=40, l=50, r=20),
        height=340,
        xaxis_title="Hour (UTC)",
        yaxis_title="Avg views/hr",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.info(f"Chart not available yet: {e}")

st.divider()

# ── Best windows table ────────────────────────────────────────────────────

if top_windows:
    st.subheader("🏆 Best upload windows")
    rows = []
    for w in top_windows:
        ist = (w["hour"] + 5) % 24
        rows.append({
            "UTC Hour": f"{w['hour']:02d}:00",
            "IST (approx)": f"{ist:02d}:30",
            "Avg views/hr": f"{w['avg_velocity']:.1f}",
            "Data points": w["sample_count"],
        })
    df = pd.DataFrame(rows)
    df.index = (["🥇", "🥈", "🥉"] + [f"{i+4}th" for i in range(len(df) - 3)])[:len(df)]
    st.dataframe(df, use_container_width=True)
else:
    st.info("No upload windows yet — need more snapshot data.")

st.divider()

# ── How it works ──────────────────────────────────────────────────────────

with st.expander("How adaptive scheduling works"):
    st.markdown("""
**Phase 4 logic:**

1. Every hour, the view tracker records how many views each video gained
2. It calculates *velocity* = views gained ÷ hours elapsed for each snapshot pair
3. It groups velocities by the UTC hour they were recorded
4. The hour with the highest average velocity = best upload time

**English, Hindi, and Cricket channels are tracked completely separately** — different audiences,
different timezones, different peak hours. This page shows whichever channel you select above.
Cricket's data lives in its own Supabase Postgres database (Render free tier has no persistent
disk), while English/Hindi share the SQLite database.

**Scheduler behavior:**
- If best hour is within 90 minutes → waits and uploads at that hour
- If best hour is more than 90 minutes away → uploads immediately (doesn't waste time)
- If not enough data yet → uploads immediately

**Why this matters:**
YouTube's algorithm boosts videos hardest in the first 30 minutes after upload.
If you upload when your audience is most active, those first 30 minutes get maximum views,
which triggers the algorithm to push the video to more people.
""")

st.caption(f"Data source: {source} · Channel: {channel} · Refreshes every 5 min · {now_utc.strftime('%Y-%m-%d %H:%M')} UTC")
CRICKETEOF
echo 'Wrote pages/schedule.py'

mkdir -p $(dirname pages/1_Dashboard.py)
cat > pages/1_Dashboard.py << 'CRICKETEOF'
import streamlit as st
import os
import glob

st.set_page_config(
    page_title="AI CarryON",
    page_icon="🤖",
    layout="wide"
)

from agents.dashboard_sync import sync_all_channel_data
_sync_status = sync_all_channel_data()


st.markdown("""
<style>
/* ── Base ── */
[data-testid="stAppViewContainer"] { background: #0a0a0f; }
[data-testid="stSidebar"] { background: #0f0f1a; border-right: 1px solid #1e1e2e; }
section.main > div { padding-top: 1.5rem; }

/* ── Typography ── */
h1, h2, h3 { color: #e2e8f0 !important; font-family: 'Inter', sans-serif; letter-spacing: -0.5px; }
p, label, .stMarkdown { color: #94a3b8 !important; }

/* ── Tabs ── */
[data-testid="stTabs"] button {
    color: #64748b !important;
    font-weight: 600;
    border-bottom: 2px solid transparent;
    padding: 0.5rem 1.5rem;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #38bdf8 !important;
    border-bottom: 2px solid #38bdf8 !important;
    background: transparent !important;
}

/* ── Primary button ── */
[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #0ea5e9, #6366f1) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.6rem 2rem !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    letter-spacing: 0.5px !important;
    box-shadow: 0 0 20px rgba(14,165,233,0.3) !important;
    transition: all 0.2s ease !important;
}
[data-testid="stButton"] > button[kind="primary"]:hover {
    box-shadow: 0 0 30px rgba(14,165,233,0.5) !important;
    transform: translateY(-1px) !important;
}

/* ── Secondary buttons ── */
[data-testid="stButton"] > button {
    background: #1e1e2e !important;
    color: #94a3b8 !important;
    border: 1px solid #2d2d3d !important;
    border-radius: 8px !important;
}

/* ── Input ── */
[data-testid="stTextInput"] input {
    background: #1e1e2e !important;
    border: 1px solid #2d2d3d !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
    font-size: 1rem !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #38bdf8 !important;
    box-shadow: 0 0 0 2px rgba(56,189,248,0.15) !important;
}

/* ── Radio ── */
[data-testid="stRadio"] label { color: #94a3b8 !important; }
[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p { color: #e2e8f0 !important; }

/* ── Toggle ── */
[data-testid="stToggle"] label { color: #94a3b8 !important; }

/* ── Info / Success / Warning boxes ── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    border-left-width: 3px !important;
}

/* ── Code blocks (prompts) ── */
[data-testid="stCode"] {
    background: #1e1e2e !important;
    border: 1px solid #2d2d3d !important;
    border-radius: 8px !important;
    white-space: pre-wrap !important;
    word-break: break-word !important;
}
[data-testid="stCode"] code {
    color: #7dd3fc !important;
    font-size: 0.85rem !important;
    line-height: 1.6 !important;
}

/* ── Divider ── */
hr { border-color: #1e1e2e !important; }

/* ── Selectbox ── */
[data-testid="stSelectbox"] > div > div {
    background: #1e1e2e !important;
    border: 1px solid #2d2d3d !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: #1e1e2e !important;
    border: 1px dashed #2d2d3d !important;
    border-radius: 8px !important;
    padding: 1rem !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: #1e1e2e;
    border: 1px solid #2d2d3d;
    border-radius: 10px;
    padding: 1rem;
}
[data-testid="stMetricValue"] { color: #38bdf8 !important; }

/* ── Spinner ── */
[data-testid="stSpinner"] { color: #38bdf8 !important; }
</style>
""", unsafe_allow_html=True)

def show_analytics():
    st.title("📊 YouTube Analytics Dashboard")
    col_refresh, col_auto, col_last = st.columns([1, 2, 3])
    with col_refresh:
        refresh = st.button("🔄 Refresh Now")
    with col_auto:
        auto_refresh = st.toggle("⏱️ Auto-refresh every 30 min", value=False)
    import time
    if "last_refresh" not in st.session_state:
        st.session_state["last_refresh"] = time.time()
    if auto_refresh:
        elapsed = time.time() - st.session_state["last_refresh"]
        remaining = max(0, 1800 - int(elapsed))
        mins, secs = divmod(remaining, 60)
        with col_last:
            st.caption(f"⏳ Next refresh in: {mins:02d}:{secs:02d}")
        if elapsed >= 1800:
            st.session_state["last_refresh"] = time.time()
            st.rerun()
    if refresh:
        st.session_state["last_refresh"] = time.time()
        st.rerun()
    with st.spinner("Fetching channel data..."):
        from agents.analytics_agent import get_channel_stats, get_recent_videos
        stats = get_channel_stats()
        videos = get_recent_videos(20)
    if auto_refresh:
        import streamlit as _st
        _st.markdown('<meta http-equiv="refresh" content="1800">', unsafe_allow_html=True)
    st.subheader("📡 Channel Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👤 Subscribers", f"{stats['subscribers']:,}")
    col2.metric("👁️ Total Views", f"{stats['total_views']:,}")
    col3.metric("🎬 Videos", f"{stats['video_count']:,}")
    if videos:
        avg_views = sum(v['views'] for v in videos) // len(videos)
        col4.metric("📈 Avg Views", f"{avg_views:,}")
    st.divider()
    if not videos:
        st.info("No videos found.")
        return
    st.subheader("🏆 Top Videos by Views")
    import pandas as pd
    df = pd.DataFrame(videos)
    df['short_title'] = df['title'].str[:30] + "..."
    st.bar_chart(df.set_index('short_title')['views'])
    st.divider()
    st.subheader("📋 All Videos")
    for v in videos:
        with st.container():
            c1, c2, c3, c4, c5 = st.columns([4, 1, 1, 1, 1])
            c1.markdown(f"[{v['title']}]({v['url']})")
            c2.markdown(f"👁️ **{v['views']:,}**")
            c3.markdown(f"👍 {v['likes']:,}")
            c4.markdown(f"💬 {v['comments']:,}")
            c5.markdown(f"📅 {v['published']}")
        st.divider()

# ── Password protection ──────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔐 AI CarryON - Login")
    st.info(
        "This panel is password protected — it controls live video generation and "
        "uploads to real YouTube channels using API credentials, so public access isn't allowed."
    )
    password = st.text_input("Enter Password", type="password")
    if st.button("Login"):
        if password == os.getenv("APP_PASSWORD", "aicarryon2026"):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Wrong password!")
    st.stop()

# ── Main Tabs ────────────────────────────────────────────────────
english_tab, hindi_tab, cricket_tab = st.tabs(["🇬🇧 English Channel", "🇮🇳 Hindi Channel", "🏏 Cricket Channel"])

# ════════════════════════════════════════════════════════════════
# ENGLISH CHANNEL
# ════════════════════════════════════════════════════════════════
with english_tab:
    page = st.sidebar.selectbox("📂 Navigation", ["🎬 Generate Video", "📊 Analytics", "🕵️ Trending Spy"])

    if st.session_state.get("go_generate"):
        st.session_state["go_generate"] = False
        page = "🎬 Generate Video"

    if page == "🕵️ Trending Spy":
        st.title("🕵️ Trending Spy")
        st.markdown("Top performing Shorts from leading AI/Tech channels — click to generate your own version!")
        with st.spinner("Fetching trending topics from top channels..."):
            from agents.spy_agent import get_trending_topics
            topics = get_trending_topics()
        if not topics:
            st.warning("No topics found.")
            st.stop()
        for t in topics:
            with st.container():
                c1, c2, c3, c4, c5 = st.columns([4, 1, 1, 1, 2])
                c1.markdown(f"[{t['title']}]({t['url']})")
                c2.markdown(f"📺 **{t['channel']}**")
                c3.markdown(f"👁️ {t['views']:,}")
                c4.markdown(f"👍 {t['likes']:,}")
                if c5.button("🎬 Make This Video", key=t['url']):
                    st.session_state["trending_topic"] = t["topic"]
                    st.session_state["go_generate"] = True
                    st.rerun()
            st.divider()

    elif page == "📊 Analytics":
        show_analytics()

    else:
        # Generate Video page
        from agents.research_agent import research
        from agents.script_agent import create_script
        from agents.seo_agent import generate_seo
        from agents.thumbnail_agent import generate_thumbnail_text
        from agents.thumbnail_generator import generate_thumbnail
        from agents.image_agent import generate_backgrounds
        from agents.voice_agent import generate_voice
        from agents.caption_agent import create_srt
        from agents.video_agent import create_video
        from agents.manim_agent import render_manim_animation
        from agents.upload_agent import upload_video

        st.title("🤖 AI CarryON")
        st.markdown("Generate AI-powered YouTube Shorts automatically")

        topic = st.text_input(
            "Enter Topic",
            placeholder="What is LangChain?",
            value=st.session_state.get("trending_topic", ""),
            key="english_topic_input"
        )

        if st.button("🔥 Use Trending Topic Instead"):
            with st.spinner("Fetching trending topic..."):
                from agents.trending_agent import get_trending_topic
                try:
                    trending = get_trending_topic()
                    st.session_state["trending_topic"] = trending
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        if "trending_topic" in st.session_state:
            topic = st.session_state["trending_topic"]
            st.success(f"Trending topic: **{topic}**")

        auto_upload = st.toggle("Auto-upload to YouTube after generation", value=False)

        st.markdown("---")
        st.markdown("**🎬 Video Background Mode**")
        video_mode_pre = st.radio(
            "Video Background Mode",
            ["🎥 Flow clips — cinematic AI video (recommended)", "🖼️ Auto image backgrounds — no upload needed"],
            index=0,
            label_visibility="collapsed",
            key="video_mode_radio",
            horizontal=True
        )
        if "Flow clips" in video_mode_pre:
            st.info("📋 After generating, copy the Veo prompts → go to [labs.google/flow](https://labs.google/flow) → generate VIDEO clips → download MP4s → upload them back here")
        else:
            st.info("🖼️ Pexels backgrounds will be generated automatically — no upload needed")
        st.markdown("---")

        col_gen, col_clear = st.columns([3, 1])
        with col_gen:
            generate_clicked = st.button("Generate", type="primary")
        with col_clear:
            if st.button("🔄 New Topic"):
                for k in ["eng_research","eng_script","eng_seo","eng_prompts","eng_thumb_text","eng_thumb_img","eng_topic_done"]:
                    st.session_state.pop(k, None)
                st.rerun()

        if generate_clicked:
            if not topic.strip():
                st.warning("Please enter a topic.")
                st.stop()
            st.session_state["eng_topic_done"] = topic
            try:
                with st.spinner("🔍 Researching..."):
                    st.session_state["eng_research"] = research(topic)
                with st.spinner("✍️ Generating Script..."):
                    st.session_state["eng_script"] = create_script(st.session_state.get("eng_research", ""))
                with st.spinner("📈 Generating SEO..."):
                    st.session_state["eng_seo"] = generate_seo(topic, st.session_state.get("eng_script", ""))
                with st.spinner("🎬 Generating Flow/Veo Prompts..."):
                    from agents.flow_prompt_agent import generate_flow_prompts
                    st.session_state["eng_prompts"] = generate_flow_prompts(topic, st.session_state.get("eng_script", ""), num_clips=3)
                with st.spinner("🎯 Generating Thumbnail Text..."):
                    st.session_state["eng_thumb_text"] = generate_thumbnail_text(topic)
                with st.spinner("🖼️ Generating Thumbnail Image..."):
                    st.session_state["eng_thumb_img"] = generate_thumbnail(st.session_state.get("eng_seo", {}).get("title", ""), topic)

            except Exception as e:
                st.error(f"Generation failed: {e}")
                st.stop()

        if st.session_state.get("eng_topic_done"):
            research_data = st.session_state.get("eng_research", "")
            script = st.session_state.get("eng_script", "")
            seo = st.session_state.get("eng_seo", {})
            flow_prompts = st.session_state.get("eng_prompts", [])
            thumbnail_text = st.session_state.get("eng_thumb_text", "")
            thumbnail_image = st.session_state.get("eng_thumb_img", "")

            try:
                st.subheader("📚 Research")
                st.write(research_data)
                st.subheader("📝 YouTube Script")
                st.write(script)
                st.subheader("📈 SEO")
                st.markdown(f"**Title:** {seo['title']}")
                st.markdown(f"**Description:** {seo['description']}")
                st.markdown(f"**Hashtags:** {seo['hashtags']}")

                use_flow_clips = "Flow clips" in st.session_state.get("video_mode_radio", "")

                # ── Flow Prompts ──────────────────────────────────
                st.divider()
                st.subheader("🎬 Flow / Veo 3 Cinematic Prompts")
                if use_flow_clips:
                    st.info("📋 **Step 1:** Copy prompt → **Step 2:** Paste in [labs.google/flow](https://labs.google/flow) → Generate VIDEO → **Step 3:** Download MP4 → **Step 4:** Upload below")
                else:
                    st.caption("💡 Reference prompts — auto image mode is active")

                for i, fp in enumerate(flow_prompts):
                    st.markdown(f"**Clip {i+1}**")
                    st.code(fp, language=None)

                if use_flow_clips:
                    st.subheader("📤 Upload Your Flow Clips")
                    uploaded_clips = st.file_uploader(
                        "Upload all MP4 clips here, then scroll down to Generate Video",
                        type=["mp4", "mov"],
                        accept_multiple_files=True,
                        key="flow_clips_uploader"
                    )
                    if uploaded_clips:
                        os.makedirs("assets/flow_clips", exist_ok=True)
                        for f in glob.glob("assets/flow_clips/*.mp4"):
                            os.remove(f)
                        for i, clip in enumerate(uploaded_clips):
                            clip_path = f"assets/flow_clips/clip_{i:02d}.mp4"
                            with open(clip_path, "wb") as f:
                                f.write(clip.read())
                        st.success(f"✅ {len(uploaded_clips)} clip(s) ready — cinematic video mode active")
                    else:
                        if os.path.isdir("assets/flow_clips"):
                            for f in glob.glob("assets/flow_clips/*.mp4"):
                                os.remove(f)
                        st.warning("⬆️ Upload your downloaded Flow clips above to proceed with cinematic mode")
                else:
                    if os.path.isdir("assets/flow_clips"):
                        for f in glob.glob("assets/flow_clips/*.mp4"):
                            os.remove(f)

                st.subheader("🖼️ Thumbnail Text")
                st.success(thumbnail_text)
                st.subheader("🖼️ Thumbnail Image")
                st.image(thumbnail_image, width="stretch")

                # Skip Pexels if Flow clips mode is active
                _flow_clips_exist = bool(glob.glob("assets/flow_clips/*.mp4"))
                _use_flow = "Flow clips" in st.session_state.get("video_mode_radio", "")
                if _use_flow and not _flow_clips_exist:
                    st.warning("⏸️ Flow clips mode is ON — upload your 3 clips above first, then click Generate Video below")
                    st.stop()
                elif _flow_clips_exist:
                    image_paths, image_errors = [], []
                    st.success("🎥 Flow clips detected — using cinematic clips")
                else:
                    with st.spinner("🎨 Generating Background Images..."):
                        image_paths, image_errors = generate_backgrounds(topic, script, num_images=4)
                if image_errors:
                    st.warning("Some images failed to generate:")
                    for err in image_errors:
                        st.text(err)
                if image_paths:
                    st.subheader("🖼️ Generated Backgrounds")
                    cols = st.columns(len(image_paths))
                    for col, img_path in zip(cols, image_paths):
                        col.image(img_path)
                elif not (_use_flow or _flow_clips_exist):
                    st.error("No background images were generated. Cannot continue.")
                    st.stop()

                with st.spinner("🎤 Generating Voiceover..."):
                    voice_file = generate_voice(script)
                st.subheader("🔊 Voiceover")
                st.audio(voice_file)

                with st.spinner("✏️ Generating Captions..."):
                    caption_file = create_srt(script, voice_file)
                st.subheader("📄 Captions")
                st.code(open(caption_file).read())

                if st.button("🎬 Generate Final Video", key="eng_make_video_btn", type="primary"):
                    with st.spinner("🎬 Creating Final Video..."):
                        video_file = create_video(manim_path=None, use_flow_clips=_flow_clips_exist)
                    st.session_state["eng_video_file"] = video_file

                from moviepy import AudioFileClip as AFC
                duration = AFC("output/voice.mp3").duration
                if duration > 60:
                    st.warning(f"⚠️ Video is {duration:.1f}s — over 60s Shorts limit!")
                else:
                    st.success(f"✅ Shorts-ready! Duration: {duration:.1f}s")

                st.subheader("🎥 Generated Video")
                st.video(video_file)
                st.success("✅ Video Created Successfully!")

                with open(video_file, "rb") as f:
                    st.download_button(
                        label="📱 Download for Instagram Reels",
                        data=f,
                        file_name="reel.mp4",
                        mime="video/mp4"
                    )

                st.info("""**📱 Post to Instagram Reels manually:**
1. Download the video above
2. Open Instagram on your phone
3. Tap **+** → **Reel**
4. Select the downloaded video
5. Add caption and post!""")

                if auto_upload:
                    with st.spinner("📤 Uploading to YouTube..."):
                        video_id, video_url = upload_video(
                            video_path=video_file,
                            title=seo["title"],
                            description=seo["description"],
                            hashtags=seo["hashtags"],
                            thumbnail_path=thumbnail_image
                        )
                    st.subheader("📤 YouTube Upload")
                    st.success("Uploaded successfully!")
                    st.markdown(f"**Watch here:** [{video_url}]({video_url})")
                else:
                    st.info("Auto-upload is OFF. Toggle it on to upload directly to YouTube.")

            except Exception as e:
                st.error(str(e))

# ════════════════════════════════════════════════════════════════
# HINDI CHANNEL
# ════════════════════════════════════════════════════════════════
with hindi_tab:
    # Handle redirect from Banao button
    if st.session_state.get("hindi_nav_override"):
        st.session_state["hindi_page_current"] = st.session_state["hindi_nav_override"]
        st.session_state["hindi_nav_override"] = None

    hindi_nav_options = ["🎬 Video Banao", "📊 Analytics", "🕵️ Trending Spy"]
    current_page = st.session_state.get("hindi_page_current", "🎬 Video Banao")
    hindi_nav_default = hindi_nav_options.index(current_page) if current_page in hindi_nav_options else 0

    hindi_page = st.sidebar.selectbox(
        "📂 Hindi Navigation",
        hindi_nav_options,
        index=hindi_nav_default,
        key="hindi_nav"
    )
    # Update current page on manual selection
    st.session_state["hindi_page_current"] = hindi_page

    # ── Trending Spy ─────────────────────────────────────────────
    if hindi_page == "🕵️ Trending Spy":
        st.title("🕵️ Hindi Trending Spy")
        st.markdown("Top Hindi Tech channels ke viral topics — click karo apna version banane ke liye!")

        with st.spinner("Hindi channels ke trending topics fetch ho rahe hain..."):
            try:
                from agents_hindi.spy_agent import get_hindi_trending_topics
                topics = get_hindi_trending_topics()
            except Exception as e:
                st.error(str(e))
                topics = []

        if not topics:
            st.warning("Koi topics nahi mile.")
        else:
            for i, t in enumerate(topics):
                with st.container():
                    c1, c2, c3, c4, c5 = st.columns([4, 1, 1, 1, 2])
                    c1.markdown(f"**{t['title']}**")
                    c2.markdown(f"📺 {t['channel']}")
                    c3.markdown(f"👁️ {t['views']:,}")
                    c4.markdown(f"🔥 {t.get('why_trending', 'Viral')[:30]}")
                    if c5.button("🎬 Banao", key=f"hindi_{i}_{t['topic'][:20]}"):
                        st.session_state["hindi_topic"] = t["topic"]
                        st.session_state["hindi_competitor"] = t
                        st.session_state["hindi_nav_override"] = "🎬 Video Banao"
                        st.rerun()
                st.divider()

    # ── Analytics ────────────────────────────────────────────────
    elif hindi_page == "📊 Analytics":
        st.title("📊 Hindi Channel Analytics")
        st.info("Hindi channel analytics coming soon! Railway deploy ke baad available hoga.")

    # ── Generate Video ───────────────────────────────────────────
    else:
        from agents_hindi.script_agent import create_script as hindi_create_script
        from agents_hindi.seo_agent import generate_seo as hindi_generate_seo
        from agents_hindi.voice_agent import generate_voice as hindi_generate_voice
        from agents_hindi.trending_agent import get_trending_topic as hindi_get_trending

        st.title("🇮🇳 AI CarryON - Hindi Channel")
        st.markdown("Hindi YouTube Shorts ke liye AI-powered video banao!")

        if st.session_state.get("hindi_go_generate"):
            st.session_state["hindi_go_generate"] = False

        # Auto-fill from trending spy or trending button
        prefilled = st.session_state.get("hindi_topic", "")
        hindi_topic = st.text_input(
            "Topic daalo (Hindi ya English mein)",
            placeholder="Artificial Intelligence kya hai?",
            value=prefilled,
            key="hindi_topic_input"
        )

        col_trend, col_clear = st.columns([2, 1])
        with col_trend:
            if st.button("🔥 Trending Topic Lo (India)", key="hindi_trending_btn"):
                with st.spinner("India ka trending topic fetch ho raha hai..."):
                    try:
                        t = hindi_get_trending(region_code="IN")
                        st.session_state["hindi_topic"] = t
                        st.session_state["hindi_competitor"] = None
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
        with col_clear:
            if st.button("🗑️ Clear", key="hindi_clear_btn"):
                st.session_state.pop("hindi_topic", None)
                st.session_state.pop("hindi_competitor", None)
                st.rerun()

        if st.session_state.get("hindi_topic"):
            st.success(f"✅ Topic ready: **{st.session_state['hindi_topic']}**")
            if st.session_state.get("hindi_competitor"):
                st.caption(f"📺 Source: {st.session_state['hindi_competitor'].get('channel', '')} — {st.session_state['hindi_competitor'].get('why_trending', '')}")

        hindi_upload = st.toggle(
            "Auto-upload to Hindi YouTube Channel",
            value=False,
            key="hindi_upload_toggle"
        )

        if st.button("🎬 Hindi Video Banao", key="hindi_generate_btn"):
            if not hindi_topic.strip():
                st.warning("Pehle topic daalo!")
            else:
                try:
                    with st.spinner("🔍 Research ho raha hai..."):
                        from agents.research_agent import research
                        st.session_state["hindi_research"] = research(hindi_topic)
                    with st.spinner("✍️ Hindi script likh raha hai..."):
                        st.session_state["hindi_script"] = hindi_create_script(st.session_state["hindi_research"])
                    with st.spinner("📈 Hindi SEO generate ho raha hai..."):
                        competitor_data = st.session_state.get("hindi_competitor", None)
                        st.session_state["hindi_seo"] = hindi_generate_seo(hindi_topic, st.session_state["hindi_script"], competitor_data=competitor_data)
                    with st.spinner("🖼️ Thumbnail ban raha hai..."):
                        from agents.thumbnail_generator import generate_thumbnail
                        st.session_state["hindi_thumb"] = generate_thumbnail(st.session_state["hindi_seo"]["title"], hindi_topic)
                    with st.spinner("🌆 Background images fetch ho rahi hain..."):
                        from agents.image_agent import generate_backgrounds
                        imgs, errs = generate_backgrounds(hindi_topic, st.session_state["hindi_script"], num_images=4)
                        st.session_state["hindi_images"] = imgs
                        st.session_state["hindi_img_errors"] = errs
                    with st.spinner("🎙️ Hindi awaaz generate ho rahi hai..."):
                        st.session_state["hindi_voice"] = hindi_generate_voice(st.session_state["hindi_script"])
                    with st.spinner("💬 Captions ban rahe hain..."):
                        from agents.caption_agent import create_srt
                        st.session_state["hindi_captions"] = create_srt(st.session_state["hindi_script"], st.session_state["hindi_voice"])
                    with st.spinner("🎬 Flow/Veo Prompts generate ho rahe hain..."):
                        from agents_hindi.flow_prompt_agent import generate_flow_prompts_hindi
                        st.session_state["hindi_prompts"] = generate_flow_prompts_hindi(
                            st.session_state.get("hindi_topic", ""), st.session_state["hindi_script"]
                        )
                    st.session_state["hindi_generated"] = True
                    st.session_state["hindi_video_file"] = None
                except Exception as e:
                    st.error(str(e))
                    import traceback
                    st.code(traceback.format_exc())

        # ── Display all generated content from session state ──
        if st.session_state.get("hindi_generated"):
                research_data = st.session_state.get("hindi_research", "")
                script = st.session_state.get("hindi_script", "")
                seo = st.session_state.get("hindi_seo", {})

                st.subheader("📚 Research")
                st.write(research_data)
                st.subheader("📝 Hindi Script")
                st.write(script)
                st.subheader("📈 SEO")
                st.markdown(f"**Title:** {seo.get('title','')}")
                st.markdown(f"**Description:** {seo.get('description','')}")
                st.markdown(f"**Hashtags:** {seo.get('hashtags','')}")

                st.subheader("🖼️ Thumbnail")
                st.image(st.session_state.get("hindi_thumb"), width="stretch")

                image_paths = st.session_state.get("hindi_images", [])
                image_errors = st.session_state.get("hindi_img_errors", [])
                if image_errors:
                    for err in image_errors:
                        st.warning(err)
                if image_paths:
                    st.subheader("🖼️ Background Images")
                    cols = st.columns(len(image_paths))
                    for col, img_path in zip(cols, image_paths):
                        col.image(img_path)

                voice = st.session_state.get("hindi_voice")
                st.subheader("🔊 Hindi Awaaz")
                if voice:
                    st.audio(voice)

                caption_file = st.session_state.get("hindi_captions")
                st.subheader("📄 Captions")
                if caption_file:
                    st.code(open(caption_file).read())

                hindi_flow_prompts = st.session_state.get("hindi_prompts", [])

                st.subheader("🎬 Flow Video Prompts (Google Flow / Veo 3)")
                st.info("Har prompt copy karo → labs.google/flow mein paste karo → clip download karo → neeche upload karo")

                for i, fp in enumerate(hindi_flow_prompts):
                    st.code(fp, language=None)

                st.divider()
                st.subheader("🎬 Video Mode Chuno")

                col_auto, col_flow = st.columns(2)
                with col_auto:
                    if st.button("🤖 Auto (Pexels images)", key="hindi_mode_auto",
                                 type="primary" if st.session_state.get("hindi_mode") != "flow" else "secondary"):
                        st.session_state["hindi_mode"] = "auto"
                        if os.path.isdir("assets/flow_clips"):
                            for f in glob.glob("assets/flow_clips/*.mp4"):
                                os.remove(f)
                with col_flow:
                    if st.button("🎬 Flow clips use karo", key="hindi_mode_flow",
                                 type="primary" if st.session_state.get("hindi_mode") == "flow" else "secondary"):
                        st.session_state["hindi_mode"] = "flow"

                hindi_mode = st.session_state.get("hindi_mode", "auto")

                if hindi_mode == "flow":
                    st.success("✅ Flow clips mode active hai")
                    st.markdown("**📤 Teeno clips upload karo (MP4):**")
                    hindi_uploaded_clips = st.file_uploader(
                        "Flow clips upload karo",
                        type=["mp4", "mov"],
                        accept_multiple_files=True,
                        key="hindi_flow_clips_uploader"
                    )
                    if hindi_uploaded_clips:
                        os.makedirs("assets/flow_clips", exist_ok=True)
                        for f in glob.glob("assets/flow_clips/*.mp4"):
                            os.remove(f)
                        for i, clip in enumerate(hindi_uploaded_clips):
                            clip_path = f"assets/flow_clips/clip_{i:02d}.mp4"
                            with open(clip_path, "wb") as f:
                                f.write(clip.read())
                        st.success(f"✅ {len(hindi_uploaded_clips)} clip(s) upload ho gaye!")
                    else:
                        st.warning("⚠️ Abhi tak koi clip upload nahi hua — clips upload karo phir Video Banao click karo")
                else:
                    st.info("🤖 Auto mode — Pexels se background images use honge")
                    if os.path.isdir("assets/flow_clips"):
                        for f in glob.glob("assets/flow_clips/*.mp4"):
                            os.remove(f)

                _hindi_clips_exist = bool(glob.glob("assets/flow_clips/*.mp4"))
                _hindi_use_flow = hindi_mode == "flow"

                if _hindi_use_flow and not _hindi_clips_exist:
                    st.warning("⬆️ Pehle clips upload karo, phir Video Banao click karo")
                else:
                    if st.button("🎬 Video Banao (Final)", key="hindi_make_video_btn", type="primary"):
                        with st.spinner("🎬 Video ban raha hai..."):
                            from agents.video_agent import create_video
                            st.session_state["hindi_video_file"] = create_video(use_flow_clips=_hindi_clips_exist)
                            for _f in glob.glob("assets/flow_clips/*.mp4"):
                                os.remove(_f)

                video_file = st.session_state.get("hindi_video_file")
                if video_file:
                    from moviepy import AudioFileClip as AFC
                    duration = AFC("output/voice.mp3").duration
                    if duration > 60:
                        st.warning(f"⚠️ Video {duration:.1f}s ka hai — 60s Shorts limit se zyada!")
                    else:
                        st.success(f"✅ Shorts-ready! Duration: {duration:.1f}s")

                    st.subheader("🎥 Generated Hindi Video")
                    st.video(video_file)
                    st.success("✅ Video ban gaya!")

                    with open(video_file, "rb") as f:
                        st.download_button(
                            label="📱 Instagram Reels ke liye Download karo",
                            data=f,
                            file_name="hindi_reel.mp4",
                            mime="video/mp4",
                            key="hindi_download"
                        )

                    if hindi_upload:
                        with st.spinner("📤 YouTube Hindi channel par upload ho raha hai..."):
                            from agents_hindi.upload_agent import upload_video as hindi_upload_fn
                            video_id, video_url = hindi_upload_fn(
                                video_path=video_file,
                                title=seo.get("title",""),
                                description=seo.get("description",""),
                                hashtags=seo.get("hashtags",""),
                                thumbnail_path=st.session_state.get("hindi_thumb")
                            )
                        st.success("✅ YouTube par upload ho gaya!")
                        st.balloons()
                        st.markdown(f"**▶️ Yahan dekho:** [{video_url}]({video_url})")
                        st.session_state.pop("hindi_topic", None)
                        st.session_state.pop("hindi_competitor", None)
                    else:
                        st.info("💡 Auto-upload OFF hai. Toggle on karo YouTube par seedha upload karne ke liye.")

# ════════════════════════════════════════════════════════════════
# CRICKET CHANNEL (fully automated — same pipeline as Render)
# ════════════════════════════════════════════════════════════════
with cricket_tab:
    cricket_page = st.sidebar.selectbox(
        "📂 Cricket Navigation", ["🎬 Generate + Upload", "📊 Analytics"], key="cricket_nav"
    )

if cricket_page == "📊 Analytics":
    with cricket_tab:
        st.title("📊 Cricket Channel Analytics")
        st.caption("Live stats pulled from the cricket channel's own YouTube credentials, and snapshot history from its Supabase Postgres database.")

        col_refresh, col_track = st.columns([1, 2])
        with col_refresh:
            if st.button("🔄 Refresh", key="cricket_analytics_refresh"):
                st.rerun()
        with col_track:
            if st.button("📸 Track views now", key="cricket_track_now",
                         help="Manually pull current view counts for cricket videos into Postgres — normally happens automatically ~hourly."):
                with st.spinner("Fetching current view counts from YouTube..."):
                    try:
                        from agents_cricket.view_tracker_agent import track_views_cricket
                        tracked = track_views_cricket()
                        st.success(f"✅ Tracked {len(tracked)} cricket video(s)")
                    except Exception as e:
                        st.error(f"Tracking failed: {e}")

        st.divider()

        with st.spinner("Fetching cricket channel data..."):
            try:
                from agents_cricket.analytics_agent import get_channel_stats, get_recent_videos
                cricket_stats = get_channel_stats()
                cricket_videos = get_recent_videos(20)
                cricket_fetch_error = None
            except Exception as e:
                cricket_stats, cricket_videos = None, []
                cricket_fetch_error = str(e)

        if cricket_fetch_error:
            st.error(f"Couldn't reach the cricket channel's YouTube API: {cricket_fetch_error}")
            st.caption("Check that CRICKET_YOUTUBE_TOKEN_B64 is set for this environment and has youtube.readonly scope.")
        else:
            st.subheader("📡 Channel Overview")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("👤 Subscribers", f"{cricket_stats['subscribers']:,}")
            c2.metric("👁️ Total Views", f"{cricket_stats['total_views']:,}")
            c3.metric("🎬 Videos", f"{cricket_stats['video_count']:,}")
            if cricket_videos:
                avg_views = sum(v["views"] for v in cricket_videos) // len(cricket_videos)
                c4.metric("📈 Avg Views", f"{avg_views:,}")

            st.divider()

            if not cricket_videos:
                st.info("No cricket videos found yet.")
            else:
                st.subheader("🏆 Top Videos by Views")
                import pandas as pd
                df = pd.DataFrame(cricket_videos)
                df["short_title"] = df["title"].str[:30] + "..."
                st.bar_chart(df.set_index("short_title")["views"])

                st.divider()
                st.subheader("📋 All Cricket Videos")
                for v in cricket_videos:
                    with st.container():
                        vc1, vc2, vc3, vc4, vc5 = st.columns([4, 1, 1, 1, 1])
                        vc1.markdown(f"[{v['title']}]({v['url']})")
                        vc2.markdown(f"👁️ **{v['views']:,}**")
                        vc3.markdown(f"👍 {v['likes']:,}")
                        vc4.markdown(f"💬 {v['comments']:,}")
                        vc5.markdown(f"📅 {v['published']}")
                    st.divider()

        st.divider()
        st.subheader("🕐 Match Post History")
        try:
            from agents_cricket.database import db as _cdb, db_init_error as _cdb_err
            if _cdb is None:
                st.info(f"Match history unavailable here: {_cdb_err}")
            else:
                posted_ids = _cdb.get_all_posted_match_ids()
                st.metric("Matches posted (all-time)", len(posted_ids))
        except Exception as e:
            st.info(f"Match history unavailable: {e}")

        st.caption("For hour-by-hour peak upload windows, see the **Peak Hours** and **Schedule** pages in the sidebar — select \"Cricket AI CarryON\" there.")

    st.stop()

with cricket_tab:
    st.title("🏏 AI CarryON - Cricket Channel")
    st.markdown("Finds a recently finished match, writes the recap, generates voice/video, and uploads to YouTube — fully automatic.")
    st.caption("This runs the same pipeline that fires automatically on Render every ~20 min. Use this to trigger a cycle manually anytime.")

    st.markdown("---")

    cricket_generate_clicked = st.button(
        "🔥 Find Trending Match & Generate + Upload",
        type="primary",
        key="cricket_auto_generate_btn"
    )

    if cricket_generate_clicked:
        with st.spinner("Checking for recently finished matches..."):
            try:
                from agents_cricket.trending_agent import get_finished_matches
                matches = get_finished_matches(limit=5)
            except Exception as e:
                st.error(f"Error fetching matches: {e}")
                matches = []

        if not matches:
            st.warning("No recently finished T20/ODI/Test matches found right now. Try again later.")
        else:
            st.info(f"Found {len(matches)} finished match(es) — processing the newest one not already posted...")

            with st.spinner("Running full pipeline: research → script → SEO → voice → video → upload... this can take 1-2 minutes"):
                try:
                    from scheduler_cricket import run_cricket_cycle
                    result = run_cricket_cycle()
                except Exception as e:
                    st.error(f"Pipeline error: {e}")
                    result = None

            if result:
                status = result.get("status")
                if status == "uploaded":
                    st.success("✅ Uploaded to Cricket channel!")
                    st.balloons()
                    st.markdown(f"**Title:** {result.get('title','')}")
                    video_url = result.get("video_url", "")
                    st.markdown(f"**▶️ Watch here:** [{video_url}]({video_url})")
                elif status == "no_new_match":
                    st.info("All recently finished matches have already been posted. Nothing new right now.")
                elif status == "scorecard_fetch_failed":
                    st.warning(f"Could not fetch the scorecard for {result.get('match','')}. Try again shortly.")
                else:
                    st.info(f"Result: {result}")
CRICKETEOF
echo 'Wrote pages/1_Dashboard.py'

mkdir -p $(dirname app.py)
cat > app.py << 'CRICKETEOF'
"""
Public Portfolio Page — AI CarryON
No password gate. Safe to share with recruiters.
This is the app entry point (root URL), so it loads first automatically.
"""

import streamlit as st
import sqlite3
import os
from datetime import datetime, timezone

st.set_page_config(
    page_title="AI CarryON — Autonomous YouTube Intelligence System",
    page_icon="🤖",
    layout="wide",
)

# ─────────────────────────────────────────────
# Config — your links
# ─────────────────────────────────────────────

GITHUB_URL = "https://github.com/Unknown183-a/ai-carryon"
LINKEDIN_URL = "https://linkedin.com/in/amit-kumar-731563317"
ENGLISH_CHANNEL_URL = "https://youtube.com/@AIcarryONAI"
HINDI_CHANNEL_URL = "https://youtube.com/@AIcarryONHindi"
CRICKET_CHANNEL_URL = "https://youtube.com/@AIcarryONSports"  # update to your real handle once set
LIVE_APP_URL = "https://ai-carryon-production.up.railway.app"

DB_PATH = os.environ.get("DB_PATH", "output/aicarryon.db")

from agents.dashboard_sync import sync_all_channel_data
_sync_status = sync_all_channel_data()

# ─────────────────────────────────────────────
# Pull safe, read-only stats from SQLite (no secrets, no operational data)
# ─────────────────────────────────────────────

def get_public_stats():
    stats = {
        "total_videos": None,
        "total_snapshots": None,
        "db_available": False,
    }
    try:
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(DISTINCT video_id) FROM snapshots")
            stats["total_videos"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM snapshots")
            stats["total_snapshots"] = cur.fetchone()[0]
            stats["db_available"] = True
            conn.close()
    except Exception:
        pass
    return stats


stats = get_public_stats()

# ─────────────────────────────────────────────
# Styling
# ─────────────────────────────────────────────

st.markdown("""
<style>
.hero-badge {
    display: inline-block;
    background: rgba(34,197,94,0.15);
    color: #22c55e;
    border: 1px solid rgba(34,197,94,0.4);
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
    margin-bottom: 12px;
}
.tech-badge {
    display: inline-block;
    background: rgba(99,102,241,0.15);
    color: #a5b4fc;
    border: 1px solid rgba(99,102,241,0.3);
    padding: 4px 12px;
    border-radius: 6px;
    font-size: 0.82rem;
    margin: 3px;
}
.challenge-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 14px;
}
.phase-done {
    color: #22c55e;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Hero
# ─────────────────────────────────────────────

st.markdown('<span class="hero-badge">● Live and running in production</span>', unsafe_allow_html=True)
st.title("🤖 AI CarryON")
st.subheader("An autonomous system that researches, writes, voices, edits, and uploads YouTube videos — then learns from how they perform.")

st.markdown(
    "Three fully independent channels (English + Hindi + Cricket), each running its own "
    "scheduler, script generation, A/B title testing, and adaptive upload-time logic — "
    "with zero manual intervention after deploy."
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.link_button("🎬 Watch: English Channel", ENGLISH_CHANNEL_URL, use_container_width=True)
with col2:
    st.link_button("🎬 Watch: Hindi Channel", HINDI_CHANNEL_URL, use_container_width=True)
with col3:
    st.link_button("🏏 Watch: Cricket Channel", CRICKET_CHANNEL_URL, use_container_width=True)
with col4:
    st.link_button("💻 View Source on GitHub", GITHUB_URL, use_container_width=True)

st.caption(f"Also live: [{LIVE_APP_URL}]({LIVE_APP_URL}) · [LinkedIn]({LINKEDIN_URL})")

st.divider()

# ─────────────────────────────────────────────
# Live stats (only shown if DB has real data)
# ─────────────────────────────────────────────

if stats["db_available"] and stats["total_videos"]:
    st.markdown("### 📊 Live system stats")
    s1, s2, s3 = st.columns(3)
    s1.metric("Videos tracked", stats["total_videos"])
    s2.metric("Snapshots collected", f"{stats['total_snapshots']:,}")
    s3.metric("Channels running", "3 (English + Hindi + Cricket)")
    st.caption("Pulled live from the production database — this is real operational data, not a mockup.")
    st.divider()

# ─────────────────────────────────────────────
# What this does
# ─────────────────────────────────────────────

st.markdown("## What this system actually does")
st.markdown("""
Each channel runs an hourly-checking scheduler that, without human input:

1. Checks whether the current hour matches a data-driven peak engagement window (adaptive — falls back to safe defaults until enough data exists)
2. Fetches a trending topic, filtered against the channel's niche
3. Checks topic saturation — skips anything already covered by 20+ recent videos or major authority channels
4. Runs a competitor comparison — pulls the top 10 videos on the same topic and benchmarks views, engagement, and title/length patterns
5. Researches the topic and writes a script, tuned per channel
6. Generates 3 title variations using different psychological patterns (curiosity, urgency, revelation, contrarian, etc.), scores each, and picks a winner
7. Generates SEO description, hashtags, and a thumbnail
8. Generates background visuals (stock footage or cinematic AI clips)
9. Generates voiceover — Edge TTS for English, Sarvam AI native-language voices for Hindi
10. Renders captions and final video
11. Uploads to YouTube with full metadata
12. Records a view snapshot every hour after upload to feed back into the learning loop
""")

st.divider()

# ─────────────────────────────────────────────
# Architecture
# ─────────────────────────────────────────────

st.markdown("## Architecture")

st.code("""
Adaptive Hour Check (Phase 4)
   -> Trending Topic (niche-filtered)
   -> Saturation Check (Phase 1.5)
   -> Competitor Comparison (Phase 2)
   -> Research (Groq LLaMA 3.3-70B, Gemini fallback)
   -> Script (channel-specific length/style)
   -> A/B Title Test (Phase 3) - 3 patterns scored, winner selected
   -> SEO (description, hashtags)
   -> Thumbnail
   -> Background visuals (Pexels auto OR Flow/Veo cinematic clips)
   -> Voiceover (Edge TTS / Sarvam AI)
   -> Render + captions
   -> Upload to YouTube
   -> Hourly view snapshot -> SQLite
""", language="text")

t1, t2 = st.columns(2)
with t1:
    st.markdown("**Two independent channels, shared infrastructure:**")
    st.markdown("""
- Separate schedulers, separate learning, separate audiences
- Shared SQLite database, partitioned by `channel` so English and Hindi data never mix
- Two Railway services (web dashboard + background worker) with a shared persistent volume
""")
with t2:
    st.markdown("**Tech stack:**")
    badges = ["Python", "Streamlit", "SQLite", "Railway", "Groq (LLaMA 3.3-70B)",
              "Gemini", "Sarvam AI", "Edge TTS", "YouTube Data API", "Plotly"]
    st.markdown(" ".join(f'<span class="tech-badge">{b}</span>' for b in badges), unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────
# Phase history
# ─────────────────────────────────────────────

st.markdown("## Build timeline")
phases = [
    ("Phase 0", "Core pipeline — research, script, voice, render, upload"),
    ("Phase 1", "Velocity tracking + Peak Hours dashboard"),
    ("Phase 1.5", "Topic saturation engine — avoid duplicate/oversaturated topics"),
    ("Phase 2", "Competitor comparison — benchmark against top 10 videos per topic"),
    ("Phase 3", "A/B title testing — 3 psychological patterns scored per video"),
    ("Phase 4", "Fully adaptive scheduling — hourly checks, uploads only at data-driven peak windows"),
]
for name, desc in phases:
    st.markdown(f'<span class="phase-done">✅ {name}</span> — {desc}', unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────
# Engineering challenges — the actual resume material
# ─────────────────────────────────────────────

st.markdown("## Engineering challenges solved")
st.caption("This is the part that actually shows debugging depth, not just \"built with AI.\"")

challenges = [
    (
        "Cross-service database architecture bug",
        "The web dashboard and background worker run as separate Railway containers, each with "
        "its own filesystem. Diagnosed why the dashboard showed 'file not found' while the worker "
        "was writing real data — SQLite files don't share disk across containers without an "
        "explicit shared volume."
    ),
    (
        "Silent audio-truncation bug",
        "Hindi voiceovers were losing a portion of generated audio during the WAV-to-MP3 "
        "conversion step in the pipeline — traced it to a format handling gap and fixed the "
        "conversion path so full audio reaches the final render."
    ),
    (
        "JSON-to-SQLite migration with zero data loss",
        "Migrated view-tracking history from a flat JSON file (which was getting wiped on every "
        "Railway redeploy due to the ephemeral filesystem) to a persistent SQLite database, "
        "keeping the JSON file as a fallback loader for backward compatibility."
    ),
    (
        "Stale-cache bug after live fixes",
        "Diagnosed why a confirmed, deployed fix wasn't showing up in the UI — Streamlit's "
        "`@st.cache_data(ttl=300)` was serving a cached error response from before the fix landed. "
        "Added manual refresh controls so cache staleness stops masking real deploy status."
    ),
    (
        "Categorical-axis chart crash in Plotly",
        "A chart on the Schedule dashboard was crashing with a type error caused by mixing an "
        "hour-string label with `add_vline`'s coordinate math on a categorical x-axis. Rebuilt the "
        "'current hour' marker using `add_vrect` against label indices instead."
    ),
    (
        "Credential exposure caught before going public",
        "Found a stray `.env.save` file tracked in git history containing live API keys. Rotated "
        "every credential and used `git filter-repo` to strip the file from all 240+ commits of "
        "history before making the repository public."
    ),
]

for title, desc in challenges:
    st.markdown(f'<div class="challenge-card"><strong>{title}</strong><br>{desc}</div>', unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────

st.markdown("## Get in touch")
f1, f2, f3 = st.columns(3)
with f1:
    st.link_button("🔗 LinkedIn", LINKEDIN_URL, use_container_width=True)
with f2:
    st.link_button("💻 GitHub Repo", GITHUB_URL, use_container_width=True)
with f3:
    st.link_button("🌐 Live Dashboard", LIVE_APP_URL, use_container_width=True)

st.caption(
    "Other pages in the sidebar (Dashboard, Peak Hours, A/B Titles, Schedule, Comparison) are the "
    "operational control panel — password protected."
)

st.info(
    "🔒 **Why the other tabs are locked**\n\n"
    "Those pages include a **live \'Generate & Upload Video\' control** that publishes directly to "
    "both YouTube channels using real API credentials. If left public, anyone visiting this page "
    "could trigger uploads — including abusive, spam, or harmful content — under my channel\'s name. "
    "Keeping that panel behind a password protects the channels and keeps the system\'s real "
    "operational access private, while this Portfolio page stays fully open so you can see the "
    "architecture, the build history, and the engineering work without needing any access."
)
CRICKETEOF
echo 'Wrote app.py'

mkdir -p $(dirname requirements.txt)
cat > requirements.txt << 'CRICKETEOF'
langchain-groq
langchain
moviepy
pillow
requests
python-dotenv
google-api-python-client
google-auth-oauthlib
google-auth-httplib2
gTTS
edge-tts
schedule
imageio
imageio-ffmpeg
numpy
soundfile
streamlit
plotly
langchain-google-genai
google-genai
sarvamai
pydub
psycopg2-binary
CRICKETEOF
echo 'Wrote requirements.txt'
