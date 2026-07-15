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
