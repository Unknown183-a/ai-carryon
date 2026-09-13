"""
agents_cricket/database.py — Database for the Cricket channel.

Migrated back from Firestore to Postgres, so Cricket now shares the exact
same DATABASE_URL secret and connection pattern as English/Hindi instead of
a separate GCP project/Firestore database. Method signatures are UNCHANGED
from the Firestore version, so nothing in agents_cricket/, app_cricket.py,
scheduler_cricket.py, or pages/ needs to be touched beyond this file.

Supports two backends, chosen automatically — same rule as agents/database.py:
  - Postgres (if DATABASE_URL is set) — production / GitHub Actions.
  - SQLite (default, if DATABASE_URL is not set) — local development,
    stored at output/cricket.db.

Kept isolated via a cricket_ prefix on every table name (same isolation
goal the old "cricket_" Firestore collection prefix served):
  - cricket_videos
  - cricket_snapshots
  - cricket_meta
  - cricket_posted_matches
  - cricket_ab_tests

Usage (unchanged):
    from agents_cricket.database import db
    db.mark_posted(match_id)
    already_posted = db.get_all_posted_match_ids()
"""

import os
import json
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


def _parse_ts_safe(ts_str):
    """Parse a timestamp that may be naive or timezone-aware, always
    return a timezone-AWARE UTC datetime — same fix as agents/database.py."""
    s = ts_str.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(s)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _to_pg(query):
    """Translate sqlite-style '?' placeholders to psycopg2-style '%s'."""
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
        else:
            return self._conn.execute(query, params or ())

    def executescript(self, script):
        if self._is_pg:
            cur = self._conn.cursor()
            cur.execute(script)
        else:
            self._conn.executescript(script)


DB_PATH = os.environ.get("CRICKET_DB_PATH", "output/cricket.db")


class CricketDatabase:
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
        id_col = "id SERIAL PRIMARY KEY" if USE_POSTGRES else "id INTEGER PRIMARY KEY AUTOINCREMENT"

        with self._conn() as conn:
            conn.executescript(f"""
                CREATE TABLE IF NOT EXISTS cricket_videos (
                    video_id    TEXT PRIMARY KEY,
                    title       TEXT,
                    published   TEXT,
                    match_id    TEXT,
                    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS cricket_snapshots (
                    {id_col},
                    video_id    TEXT NOT NULL,
                    views       INTEGER DEFAULT 0,
                    likes       INTEGER DEFAULT 0,
                    comments    INTEGER DEFAULT 0,
                    timestamp   TEXT NOT NULL,
                    FOREIGN KEY (video_id) REFERENCES cricket_videos(video_id)
                );

                CREATE TABLE IF NOT EXISTS cricket_meta (
                    key    TEXT PRIMARY KEY,
                    value  TEXT
                );

                CREATE TABLE IF NOT EXISTS cricket_posted_matches (
                    match_id    TEXT PRIMARY KEY,
                    match_name  TEXT,
                    posted_at   TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cricket_ab_tests (
                    {id_col},
                    topic           TEXT,
                    winner_title    TEXT,
                    winner_pattern  TEXT,
                    winner_score    INTEGER,
                    all_variations  TEXT,
                    generated_at    TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_cricket_snapshots_video_id
                    ON cricket_snapshots(video_id);
                CREATE INDEX IF NOT EXISTS idx_cricket_snapshots_timestamp
                    ON cricket_snapshots(timestamp);
            """)

    # ── Videos ────────────────────────────────────────────────────────────

    def upsert_video(self, video_id, title, published, match_id=None):
        """Only overwrites match_id when one is given, so view_tracker's
        title/published-only refresh doesn't clobber the match_id set at
        upload time — same behavior the Firestore merge=True gave us."""
        with self._conn() as conn:
            if match_id is not None:
                conn.execute("""
                    INSERT INTO cricket_videos (video_id, title, published, match_id)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(video_id) DO UPDATE SET
                        title=excluded.title,
                        published=excluded.published,
                        match_id=excluded.match_id
                """, (video_id, title, published, match_id))
            else:
                conn.execute("""
                    INSERT INTO cricket_videos (video_id, title, published)
                    VALUES (?, ?, ?)
                    ON CONFLICT(video_id) DO UPDATE SET
                        title=excluded.title,
                        published=excluded.published
                """, (video_id, title, published))

    def get_all_videos(self):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM cricket_videos ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Snapshots ────────────────────────────────────────────────────────

    def add_snapshot(self, video_id, views, likes=0, comments=0, timestamp=None):
        if timestamp is None:
            timestamp = _now_iso()
        with self._conn() as conn:
            # Ensure a parent video row exists (mirrors the Firestore
            # version auto-creating a video doc on first snapshot).
            conn.execute("""
                INSERT INTO cricket_videos (video_id, title, published)
                VALUES (?, '', '')
                ON CONFLICT(video_id) DO NOTHING
            """, (video_id,))
            conn.execute("""
                INSERT INTO cricket_snapshots (video_id, views, likes, comments, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (video_id, views, likes, comments, timestamp))

    def get_snapshots(self, video_id):
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT views, likes, comments, timestamp FROM cricket_snapshots
                WHERE video_id = ?
                ORDER BY timestamp ASC
            """, (video_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_all_snapshots(self):
        """Return all snapshots grouped by video_id — same shape as
        agents/database.py's get_all_snapshots(), so agents_cricket.velocity_agent
        can reuse the exact same velocity-computation logic as English/Hindi."""
        with self._conn() as conn:
            videos = conn.execute("SELECT * FROM cricket_videos").fetchall()
            result = {}
            for video in videos:
                vid_id = video["video_id"]
                snapshots = conn.execute("""
                    SELECT views, likes, comments, timestamp
                    FROM cricket_snapshots WHERE video_id = ?
                    ORDER BY timestamp ASC
                """, (vid_id,)).fetchall()
                result[vid_id] = {
                    "title": video["title"],
                    "published": video["published"],
                    "match_id": video["match_id"],
                    "snapshots": [dict(s) for s in snapshots],
                }
            return result

    # ── Meta (key/value, used to throttle YouTube API calls) ──────────────

    def get_meta(self, key):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM cricket_meta WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else None

    def set_meta(self, key, value):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO cricket_meta (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """, (key, value))

    # ── Posted Matches ──────────────────────────────────────────────────────

    def mark_posted(self, match_id, match_name="", posted_at=None):
        if posted_at is None:
            posted_at = _now_iso()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO cricket_posted_matches (match_id, match_name, posted_at)
                VALUES (?, ?, ?)
                ON CONFLICT(match_id) DO NOTHING
            """, (match_id, match_name, posted_at))

    def is_posted(self, match_id):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM cricket_posted_matches WHERE match_id = ?", (match_id,)
            ).fetchone()
            return row is not None

    def get_all_posted_match_ids(self):
        with self._conn() as conn:
            rows = conn.execute("SELECT match_id FROM cricket_posted_matches").fetchall()
            return {r["match_id"] for r in rows}

    # ── A/B Title Tests ─────────────────────────────────────────────────

    def log_ab_test(self, topic, winner_title, winner_pattern, winner_score,
                     all_variations, generated_at=None):
        if generated_at is None:
            generated_at = _now_iso()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO cricket_ab_tests
                (topic, winner_title, winner_pattern, winner_score, all_variations, generated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (topic, winner_title, winner_pattern, winner_score,
                  json.dumps(all_variations), generated_at))

    def get_ab_test_stats(self, limit=200):
        """Returns raw logged tests, most recent first — same shape callers
        of agents/database.py's get_ab_test_stats() already expect."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM cricket_ab_tests
                ORDER BY generated_at DESC LIMIT ?
            """, (limit,)).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["all_variations"] = json.loads(d["all_variations"] or "[]")
                result.append(d)
            return result

    # ── Migration from Firestore (run once, from your MacBook) ─────────────

    def migrate_from_firestore(self, project=None):
        """
        One-time backfill: connects to the Firestore project cricket was
        using and writes every doc into Postgres. Run this locally BEFORE
        relying on the new DATABASE_URL-backed data — otherwise
        get_all_posted_match_ids() comes back empty and already-covered
        matches can get reposted.

        Requires google-cloud-firestore installed locally for this one call
        only — it's no longer a runtime dependency, so:
            pip install google-cloud-firestore
        """
        from google.cloud import firestore
        kwargs = {"project": project} if project else {}
        client = firestore.Client(**kwargs)
        migrated = {"videos": 0, "snapshots": 0, "posted": 0, "meta": 0, "ab_tests": 0}

        for video_doc in client.collection("cricket_videos").stream():
            v = video_doc.to_dict()
            self.upsert_video(v["video_id"], v.get("title", ""), v.get("published", ""),
                               v.get("match_id"))
            migrated["videos"] += 1
            for snap_doc in video_doc.reference.collection("snapshots").stream():
                s = snap_doc.to_dict()
                self.add_snapshot(v["video_id"], s.get("views", 0), s.get("likes", 0),
                                   s.get("comments", 0), s.get("timestamp"))
                migrated["snapshots"] += 1

        for doc in client.collection("cricket_posted_matches").stream():
            m = doc.to_dict()
            self.mark_posted(m["match_id"], m.get("match_name", ""), m.get("posted_at"))
            migrated["posted"] += 1

        for doc in client.collection("cricket_meta").stream():
            m = doc.to_dict()
            self.set_meta(doc.id, m.get("value"))
            migrated["meta"] += 1

        for doc in client.collection("cricket_ab_tests").stream():
            a = doc.to_dict()
            self.log_ab_test(a.get("topic"), a.get("winner_title"), a.get("winner_pattern"),
                              a.get("winner_score"), a.get("all_variations"), a.get("generated_at"))
            migrated["ab_tests"] += 1

        print(f"✅ Migrated from Firestore to Postgres: {migrated}")
        return migrated


# Singleton instance — same pattern as agents/database.py's `db`.
db_init_error = None
try:
    db = CricketDatabase()
except Exception as e:
    db = None
    db_init_error = str(e)
