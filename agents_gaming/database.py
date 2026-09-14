"""
agents_gaming/database.py — Database for the Gaming channel.

Same dual-backend pattern as agents_cricket/database.py: Postgres if
DATABASE_URL is set (shares the one Supabase DB used by English/Hindi/
Cricket, isolated via a gaming_ table prefix), else local SQLite at
output/gaming.db.

Tables:
  - gaming_videos         uploaded video metadata
  - gaming_meta           key/value store (daily upload cap, view-track timer)
  - gaming_posted_clips   dedup — Twitch clip IDs already turned into a video
"""
import os
from datetime import datetime, timezone
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
else:
    import sqlite3


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _to_pg(query):
    return query.replace("?", "%s")


class _CursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=None):
        self._cursor.execute(_to_pg(query), params or ())
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()


class _ConnWrapper:
    def __init__(self, conn, is_pg):
        self._conn = conn
        self._is_pg = is_pg

    def execute(self, query, params=None):
        if self._is_pg:
            cur = self._conn.cursor()
            return _CursorWrapper(cur).execute(query, params)
        return self._conn.execute(query, params or ())

    def executescript(self, script):
        if self._is_pg:
            cur = self._conn.cursor()
            cur.execute(script)
        else:
            self._conn.executescript(script)


DB_PATH = os.environ.get("GAMING_DB_PATH", "output/gaming.db")


class GamingDatabase:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        if not USE_POSTGRES:
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._init_tables()

    @contextmanager
    def _conn(self):
        if USE_POSTGRES:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield _ConnWrapper(conn, USE_POSTGRES)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_tables(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS gaming_videos (
                    video_id    TEXT PRIMARY KEY,
                    title       TEXT,
                    published   TEXT,
                    clip_id     TEXT,
                    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS gaming_meta (
                    key    TEXT PRIMARY KEY,
                    value  TEXT
                );

                CREATE TABLE IF NOT EXISTS gaming_posted_clips (
                    clip_id     TEXT PRIMARY KEY,
                    clip_title  TEXT,
                    broadcaster TEXT,
                    posted_at   TEXT NOT NULL
                );
            """)

    # ── Videos ───────────────────────────────────────────────────────────

    def upsert_video(self, video_id, title, published, clip_id=None):
        with self._conn() as conn:
            if clip_id is not None:
                conn.execute("""
                    INSERT INTO gaming_videos (video_id, title, published, clip_id)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(video_id) DO UPDATE SET
                        title=excluded.title, published=excluded.published, clip_id=excluded.clip_id
                """, (video_id, title, published, clip_id))
            else:
                conn.execute("""
                    INSERT INTO gaming_videos (video_id, title, published)
                    VALUES (?, ?, ?)
                    ON CONFLICT(video_id) DO UPDATE SET
                        title=excluded.title, published=excluded.published
                """, (video_id, title, published))

    def get_all_videos(self):
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM gaming_videos ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    # ── Dedup ────────────────────────────────────────────────────────────

    def mark_posted(self, clip_id, clip_title="", broadcaster=""):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO gaming_posted_clips (clip_id, clip_title, broadcaster, posted_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(clip_id) DO NOTHING
            """, (clip_id, clip_title, broadcaster, _now_iso()))

    def get_all_posted_clip_ids(self):
        with self._conn() as conn:
            rows = conn.execute("SELECT clip_id FROM gaming_posted_clips").fetchall()
            return {r["clip_id"] for r in rows}

    # ── Meta (daily cap, timers) ─────────────────────────────────────────

    def get_meta(self, key):
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM gaming_meta WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None

    def set_meta(self, key, value):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO gaming_meta (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, value))


try:
    db = GamingDatabase()
    db_init_error = None
except Exception as e:
    db = None
    db_init_error = str(e)
