"""
agents/database.py — Central SQLite database for AI CarryON

Replaces JSON files with a persistent SQLite database.
JSON files kept as fallback — zero data loss.

Tables:
  - videos          : YouTube video metadata
  - snapshots       : Hourly view/like counts per video
  - ab_title_tests  : A/B title test results
  - posted_topics   : Topics already posted (deduplication)
  - spy_cache       : Trending topic cache

Usage:
    from agents.database import db
    db.add_snapshot(video_id, views, likes)
    snapshots = db.get_snapshots(video_id)
"""

import os
import sqlite3
import json
from datetime import datetime, timezone
from contextlib import contextmanager

def _parse_ts_safe(ts_str):
    """
    Parse a timestamp that may be naive or timezone-aware, always
    return a timezone-AWARE UTC datetime. This fixes the bug where
    some snapshots were saved with utcnow() (naive) and others with
    datetime.now(timezone.utc) (aware), causing subtraction to fail.
    """
    from datetime import datetime as _dt, timezone as _tz
    s = ts_str.replace("Z", "+00:00")
    parsed = _dt.fromisoformat(s)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_tz.utc)
    return parsed


# Store DB in output/ folder — mount as persistent volume on Render
DB_PATH = os.environ.get("DB_PATH", "output/aicarryon.db")


class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_tables()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")  # better concurrent access
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_tables(self):
        """Create tables if they don't exist."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS videos (
                    video_id    TEXT PRIMARY KEY,
                    title       TEXT,
                    published   TEXT,
                    channel     TEXT DEFAULT 'english',
                    created_at  TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id    TEXT NOT NULL,
                    views       INTEGER DEFAULT 0,
                    likes       INTEGER DEFAULT 0,
                    comments    INTEGER DEFAULT 0,
                    timestamp   TEXT NOT NULL,
                    FOREIGN KEY (video_id) REFERENCES videos(video_id)
                );

                CREATE TABLE IF NOT EXISTS ab_title_tests (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic              TEXT,
                    winner_title       TEXT,
                    winner_pattern     TEXT,
                    winner_score       INTEGER,
                    all_variations     TEXT,
                    generated_at       TEXT,
                    actual_views       INTEGER DEFAULT NULL,
                    actual_views_24h   INTEGER DEFAULT NULL,
                    actual_checked_at  TEXT DEFAULT NULL,
                    video_id           TEXT DEFAULT NULL
                );

                CREATE TABLE IF NOT EXISTS posted_topics (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic       TEXT NOT NULL,
                    channel     TEXT DEFAULT 'english',
                    posted_at   TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS spy_cache (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel     TEXT NOT NULL,
                    topics      TEXT NOT NULL,
                    cached_at   TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_snapshots_video_id
                    ON snapshots(video_id);
                CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp
                    ON snapshots(timestamp);
                CREATE INDEX IF NOT EXISTS idx_posted_topics_channel
                    ON posted_topics(channel, posted_at);
            """)
        self._migrate_ab_title_tests_columns()

    def _migrate_ab_title_tests_columns(self):
        """
        Self-healing migration: adds columns to ab_title_tests if an
        existing (older) database is missing them. Runs on every startup,
        safe to run repeatedly — a fresh CREATE TABLE above already has
        these columns, so this is a no-op for new databases.
        """
        with self._conn() as conn:
            existing = [row["name"] for row in conn.execute("PRAGMA table_info(ab_title_tests)")]
            additions = {
                "actual_views_24h": "INTEGER DEFAULT NULL",
                "actual_checked_at": "TEXT DEFAULT NULL",
                "video_id": "TEXT DEFAULT NULL",
            }
            for col, decl in additions.items():
                if col not in existing:
                    conn.execute(f"ALTER TABLE ab_title_tests ADD COLUMN {col} {decl}")
                    print(f"Migrated ab_title_tests: added column {col}")

    # ── Videos ────────────────────────────────────────────────────────────

    def upsert_video(self, video_id, title, published, channel="english"):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO videos (video_id, title, published, channel)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    title=excluded.title,
                    published=excluded.published
            """, (video_id, title, published, channel))

    def get_video(self, video_id):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM videos WHERE video_id = ?", (video_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_videos(self, channel=None):
        with self._conn() as conn:
            if channel:
                rows = conn.execute(
                    "SELECT * FROM videos WHERE channel = ?", (channel,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM videos").fetchall()
            return [dict(r) for r in rows]

    # ── Snapshots ──────────────────────────────────────────────────────────

    def add_snapshot(self, video_id, views, likes=0, comments=0, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO snapshots (video_id, views, likes, comments, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (video_id, views, likes, comments, timestamp))

    def get_snapshots(self, video_id):
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM snapshots
                WHERE video_id = ?
                ORDER BY timestamp ASC
            """, (video_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_all_snapshots(self):
        """Return all snapshots grouped by video_id — same format as view_history.json"""
        with self._conn() as conn:
            videos = conn.execute("SELECT * FROM videos").fetchall()
            result = {}
            for video in videos:
                vid_id = video["video_id"]
                snapshots = conn.execute("""
                    SELECT views, likes, comments, timestamp
                    FROM snapshots WHERE video_id = ?
                    ORDER BY timestamp ASC
                """, (vid_id,)).fetchall()
                result[vid_id] = {
                    "title": video["title"],
                    "published": video["published"],
                    "channel": video["channel"],
                    "snapshots": [dict(s) for s in snapshots],
                }
            return result

    # ── A/B Title Tests ────────────────────────────────────────────────────

    def log_ab_test(self, topic, winner_title, winner_pattern, winner_score,
                    all_variations, generated_at=None):
        if generated_at is None:
            generated_at = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO ab_title_tests
                (topic, winner_title, winner_pattern, winner_score, all_variations, generated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (topic, winner_title, winner_pattern, winner_score,
                  json.dumps(all_variations), generated_at))

    def link_ab_test_to_video(self, winner_title, video_id):
        """
        Link the most recent unlinked ab_title_tests row matching this
        winner_title to the freshly uploaded video_id. Called right after
        a successful upload, when both values are available in the same run.
        """
        with self._conn() as conn:
            row = conn.execute("""
                SELECT id FROM ab_title_tests
                WHERE winner_title = ? AND video_id IS NULL
                ORDER BY generated_at DESC LIMIT 1
            """, (winner_title,)).fetchone()
            if row:
                conn.execute("""
                    UPDATE ab_title_tests SET video_id = ? WHERE id = ?
                """, (video_id, row["id"]))
                return True
            return False

    def get_ab_tests(self, limit=200):
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM ab_title_tests
                ORDER BY generated_at DESC LIMIT ?
            """, (limit,)).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["all_variations"] = json.loads(d["all_variations"] or "[]")
                result.append(d)
            return result

    def update_ab_actual_views(self, test_id, actual_views):
        """Update with real YouTube views after 24h — for Phase 5 learning."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE ab_title_tests SET actual_views = ?
                WHERE id = ?
            """, (actual_views, test_id))

    # ── Posted Topics ──────────────────────────────────────────────────────

    def mark_posted(self, topic, channel="english", posted_at=None):
        if posted_at is None:
            posted_at = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO posted_topics (topic, channel, posted_at)
                VALUES (?, ?, ?)
            """, (topic, channel, posted_at))

    def get_recent_posted(self, hours=24, channel="english"):
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT topic FROM posted_topics
                WHERE channel = ? AND posted_at >= ?
            """, (channel, cutoff)).fetchall()
            return [r["topic"].lower().strip() for r in rows]

    # ── Spy Cache ──────────────────────────────────────────────────────────

    def save_spy_cache(self, channel, topics):
        cached_at = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO spy_cache (channel, topics, cached_at)
                VALUES (?, ?, ?)
            """, (channel, json.dumps(topics), cached_at))

    def get_spy_cache(self, channel, max_age_seconds=21600):
        with self._conn() as conn:
            row = conn.execute("""
                SELECT * FROM spy_cache
                WHERE channel = ?
                ORDER BY cached_at DESC LIMIT 1
            """, (channel,)).fetchone()
            if not row:
                return None
            import time
            from datetime import datetime as dt
            cached_dt = dt.fromisoformat(row["cached_at"])
            age = (datetime.now(timezone.utc) - cached_dt.replace(
                tzinfo=timezone.utc)).total_seconds()
            if age > max_age_seconds:
                return None
            return json.loads(row["topics"])

    # ── Migration from JSON ────────────────────────────────────────────────

    def migrate_from_json(self, view_history_path="output/view_history.json",
                          ab_log_path="output/title_ab_log.json",
                          posted_path="output/posted_topics.txt"):
        """
        One-time migration from JSON files to SQLite.
        Safe to run multiple times — won't duplicate data.
        """
        migrated = {"videos": 0, "snapshots": 0, "ab_tests": 0, "posted": 0}

        # Migrate view_history.json
        if os.path.exists(view_history_path):
            try:
                with open(view_history_path) as f:
                    view_history = json.load(f)
                for video_id, data in view_history.items():
                    self.upsert_video(
                        video_id,
                        data.get("title", ""),
                        data.get("published", ""),
                    )
                    migrated["videos"] += 1
                    for snap in data.get("snapshots", []):
                        self.add_snapshot(
                            video_id,
                            snap.get("views", 0),
                            snap.get("likes", 0),
                            snap.get("comments", 0),
                            snap.get("timestamp"),
                        )
                        migrated["snapshots"] += 1
                print(f"✅ Migrated {migrated['videos']} videos, {migrated['snapshots']} snapshots")
            except Exception as e:
                print(f"⚠️ view_history migration error: {e}")

        # Migrate title_ab_log.json
        if os.path.exists(ab_log_path):
            try:
                with open(ab_log_path) as f:
                    ab_logs = json.load(f)
                for entry in ab_logs:
                    winner = entry.get("winner", {})
                    self.log_ab_test(
                        entry.get("topic", ""),
                        winner.get("title", ""),
                        winner.get("pattern", ""),
                        winner.get("score", 0),
                        entry.get("variations", []),
                        entry.get("generated_at"),
                    )
                    migrated["ab_tests"] += 1
                print(f"✅ Migrated {migrated['ab_tests']} A/B tests")
            except Exception as e:
                print(f"⚠️ AB log migration error: {e}")

        # Migrate posted_topics.txt
        if os.path.exists(posted_path):
            try:
                with open(posted_path) as f:
                    for line in f:
                        line = line.strip()
                        if "|" in line:
                            ts, topic = line.split("|", 1)
                            self.mark_posted(topic.strip(), posted_at=ts.strip())
                            migrated["posted"] += 1
                print(f"✅ Migrated {migrated['posted']} posted topics")
            except Exception as e:
                print(f"⚠️ Posted topics migration error: {e}")

        return migrated

    # ── Analytics ──────────────────────────────────────────────────────────

    def get_peak_hours(self):
        """
        Calculate peak upload hours from snapshot velocity data.
        Returns dict {hour: avg_velocity} based on real view data.
        """
        all_data = self.get_all_snapshots()

        from collections import defaultdict
        hour_velocities = defaultdict(list)

        for video_id, data in all_data.items():
            snapshots = data["snapshots"]
            if len(snapshots) < 2:
                continue
            for i in range(1, len(snapshots)):
                prev = snapshots[i-1]
                curr = snapshots[i]
                try:
                    t1 = _parse_ts_safe(prev["timestamp"])
                    t2 = _parse_ts_safe(curr["timestamp"])
                    hours_elapsed = (t2 - t1).total_seconds() / 3600
                    if hours_elapsed <= 0:
                        continue
                    views_gained = max(curr["views"] - prev["views"], 0)
                    velocity = views_gained / hours_elapsed
                    hour_velocities[t2.hour].append(velocity)
                except Exception:
                    continue

        result = {}
        for hour in range(24):
            values = hour_velocities.get(hour, [])
            result[hour] = {
                "avg_velocity": round(sum(values)/len(values), 4) if values else 0.0,
                "sample_count": len(values),
            }
        return result

    def get_best_upload_hour(self):
        """Return the single best hour to upload based on velocity data."""
        peak_hours = self.get_peak_hours()
        best = max(peak_hours.items(), key=lambda x: x[1]["avg_velocity"])
        if best[1]["sample_count"] < 3:
            return None  # not enough data
        return best[0]


# Singleton instance
db = Database()
