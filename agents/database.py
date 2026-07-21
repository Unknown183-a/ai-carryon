"""
agents/database.py — Central Firestore database for AI CarryON

Migrated from SQLite (Railway/Render disk) to Firestore, since Cloud Run
containers have no persistent local disk. Method signatures are UNCHANGED
from the SQLite version, so nothing in agents/ or agents_hindi/ needs to
be touched — only this file and the ~8 files that used to connect to
sqlite3 directly (see MIGRATION_NOTES.md).

Collections:
  - videos          : doc id = video_id
  - videos/{id}/snapshots : subcollection, auto id
  - ab_title_tests   : auto id
  - posted_topics    : auto id
  - spy_cache        : auto id

Usage (unchanged):
    from agents.database import db
    db.add_snapshot(video_id, views, likes)
    snapshots = db.get_snapshots(video_id)

Requires: google-cloud-firestore
Auth: uses Application Default Credentials — on Cloud Run this is automatic
      (the service's attached service account). Locally, run:
          gcloud auth application-default login
      or point FIRESTORE_EMULATOR_HOST at a local emulator for testing.
"""

import os
import json
from datetime import datetime, timezone, timedelta
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter


def _parse_ts_safe(ts_str):
    """
    Parse a timestamp that may be naive or timezone-aware, always
    return a timezone-AWARE UTC datetime. Carried over unchanged from
    the SQLite version — same bug class can still occur since we still
    store timestamps as ISO strings.
    """
    from datetime import datetime as _dt, timezone as _tz
    s = ts_str.replace("Z", "+00:00")
    parsed = _dt.fromisoformat(s)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_tz.utc)
    return parsed


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, project=None, database=None):
        # Always load .env first to get correct project
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:
            pass
        # project defaults to GOOGLE_CLOUD_PROJECT / GCLOUD_PROJECT env var,
        # which Cloud Run sets automatically. `database` lets you point at a
        # named Firestore database other than "(default)" if you want to
        # keep this fully separate from other Firebase data in the project.
        kwargs = {}
        if not project:
            import os
            project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT")
        if project:
            kwargs["project"] = project
        if database:
            kwargs["database"] = database
        self.client = firestore.Client(**kwargs)

    # ── Videos ────────────────────────────────────────────────────────────

    def upsert_video(self, video_id, title, published, channel="english"):
        ref = self.client.collection("videos").document(video_id)
        ref.set({
            "video_id": video_id,
            "title": title,
            "published": published,
            "channel": channel,
            "created_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)

    def get_video(self, video_id):
        doc = self.client.collection("videos").document(video_id).get()
        return doc.to_dict() if doc.exists else None

    def get_all_videos(self, channel=None):
        col = self.client.collection("videos")
        if channel:
            query = col.where(filter=FieldFilter("channel", "==", channel))
        else:
            query = col
        return [d.to_dict() for d in query.stream()]

    # ── Snapshots ──────────────────────────────────────────────────────────
    # Stored as a subcollection under each video doc: videos/{id}/snapshots

    def add_snapshot(self, video_id, views, likes=0, comments=0, timestamp=None):
        if timestamp is None:
            timestamp = _now_iso()
        # Ensure the parent video doc exists so get_all_videos()/joins don't break
        video_ref = self.client.collection("videos").document(video_id)
        if not video_ref.get().exists:
            video_ref.set({"video_id": video_id, "title": "", "published": "",
                           "channel": "english", "created_at": firestore.SERVER_TIMESTAMP})
        video_ref.collection("snapshots").add({
            "video_id": video_id,
            "views": views,
            "likes": likes,
            "comments": comments,
            "timestamp": timestamp,
        })

    def get_snapshots(self, video_id):
        col = self.client.collection("videos").document(video_id).collection("snapshots")
        docs = col.order_by("timestamp", direction=firestore.Query.ASCENDING).stream()
        return [d.to_dict() for d in docs]

    def get_all_snapshots(self):
        """Return all snapshots grouped by video_id — same format as before."""
        result = {}
        for video_doc in self.client.collection("videos").stream():
            video = video_doc.to_dict()
            vid_id = video["video_id"]
            snaps = self.get_snapshots(vid_id)
            result[vid_id] = {
                "title": video.get("title"),
                "published": video.get("published"),
                "channel": video.get("channel"),
                "snapshots": snaps,
            }
        return result

    # ── A/B Title Tests ────────────────────────────────────────────────────

    def log_ab_test(self, topic, winner_title, winner_pattern, winner_score,
                    all_variations, generated_at=None):
        if generated_at is None:
            generated_at = _now_iso()
        _, doc_ref = self.client.collection("ab_title_tests").add({
            "topic": topic,
            "winner_title": winner_title,
            "winner_pattern": winner_pattern,
            "winner_score": winner_score,
            "all_variations": json.dumps(all_variations),
            "generated_at": generated_at,
            "actual_views": None,
            "actual_views_24h": None,
            "actual_checked_at": None,
            "video_id": None,
        })
        return doc_ref.id  # Firestore ids are strings, unlike SQLite's int rowid

    def link_ab_test_to_video(self, winner_title, video_id):
        """
        Link the most recent unlinked ab_title_tests row matching this
        winner_title to the freshly uploaded video_id.
        NOTE: this query (equality + equality + order_by) needs a composite
        index — Firestore will raise an error with a direct "create index"
        link the first time it runs; click it once and it's done.
        """
        col = self.client.collection("ab_title_tests")
        query = (col.where(filter=FieldFilter("winner_title", "==", winner_title))
                    .where(filter=FieldFilter("video_id", "==", None))
                    .order_by("generated_at", direction=firestore.Query.DESCENDING)
                    .limit(1))
        docs = list(query.stream())
        if docs:
            docs[0].reference.update({"video_id": video_id})
            return True
        return False

    def get_ab_tests(self, limit=200):
        col = self.client.collection("ab_title_tests")
        query = col.order_by("generated_at", direction=firestore.Query.DESCENDING).limit(limit)
        result = []
        for doc in query.stream():
            d = doc.to_dict()
            d["id"] = doc.id
            d["all_variations"] = json.loads(d.get("all_variations") or "[]")
            result.append(d)
        return result

    def get_pending_ab_tests(self):
        """ab_title_tests rows where actual_views_24h hasn't been filled in yet."""
        result = []
        for doc in self.client.collection("ab_title_tests").stream():
            d = doc.to_dict()
            d["id"] = doc.id
            if d.get("actual_views_24h") is None:
                result.append(d)
        return result

    def get_video_by_title(self, title, channel=None):
        """Fallback lookup for close_ab_loop.py's title-matching path."""
        col = self.client.collection("videos")
        query = col.where(filter=FieldFilter("title", "==", title))
        if channel:
            query = query.where(filter=FieldFilter("channel", "==", channel))
        docs = list(query.limit(1).stream())
        return docs[0].to_dict() if docs else None

    def set_ab_test_video_id(self, test_id, video_id):
        self.client.collection("ab_title_tests").document(str(test_id)).update({
            "video_id": video_id
        })

    def close_ab_test(self, test_id, actual_views_24h, checked_at):
        self.client.collection("ab_title_tests").document(str(test_id)).update({
            "actual_views_24h": actual_views_24h,
            "actual_checked_at": checked_at,
        })

    def get_closed_loop_tests(self):
        """
        All ab_title_tests rows where actual_views_24h has been filled in.
        Firestore has no JOIN, so unlike the old SQLite query this does NOT
        include the video's channel/published — callers that need those
        should look them up per-row with get_video(row['video_id']).
        """
        result = []
        for doc in self.client.collection("ab_title_tests").stream():
            d = doc.to_dict()
            d["id"] = doc.id
            if d.get("actual_views_24h") is not None:
                result.append(d)
        return result

    def update_ab_actual_views(self, test_id, actual_views):
        """test_id is now a Firestore doc-id string (was an int rowid under SQLite)."""
        self.client.collection("ab_title_tests").document(str(test_id)).update({
            "actual_views": actual_views
        })

    # ── Posted Topics ──────────────────────────────────────────────────────

    def mark_posted(self, topic, channel="english", posted_at=None):
        if posted_at is None:
            posted_at = _now_iso()
        self.client.collection("posted_topics").add({
            "topic": topic,
            "channel": channel,
            "posted_at": posted_at,
        })

    def get_recent_posted(self, hours=24, channel="english"):
        """
        NOTE: equality filter (channel) + range filter (posted_at) needs a
        composite index. See firestore.indexes.json in this migration —
        deploy it with `firebase deploy --only firestore:indexes` once,
        ahead of time, so this doesn't fail on first run in production.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        col = self.client.collection("posted_topics")
        query = (col.where(filter=FieldFilter("channel", "==", channel))
                    .where(filter=FieldFilter("posted_at", ">=", cutoff)))
        return [d.to_dict()["topic"].lower().strip() for d in query.stream()]

    # ── Spy Cache ──────────────────────────────────────────────────────────

    def save_spy_cache(self, channel, topics):
        self.client.collection("spy_cache").add({
            "channel": channel,
            "topics": json.dumps(topics),
            "cached_at": _now_iso(),
        })

    def get_spy_cache(self, channel, max_age_seconds=21600):
        col = self.client.collection("spy_cache")
        query = (col.where(filter=FieldFilter("channel", "==", channel))
                    .order_by("cached_at", direction=firestore.Query.DESCENDING)
                    .limit(1))
        docs = list(query.stream())
        if not docs:
            return None
        row = docs[0].to_dict()
        cached_dt = datetime.fromisoformat(row["cached_at"])
        age = (datetime.now(timezone.utc) - cached_dt).total_seconds()
        if age > max_age_seconds:
            return None
        return json.loads(row["topics"])

    # ── Migration from SQLite (run once, from your MacBook) ────────────────

    def migrate_from_sqlite(self, sqlite_path="output/aicarryon.db"):
        """
        One-time backfill: reads your existing SQLite file and writes every
        row into Firestore. Run this locally, pointed at your real
        aicarryon.db, BEFORE cutting the schedulers over. Safe to re-run —
        upsert_video/add_snapshot etc. don't need to error on duplicates,
        but running it twice will duplicate snapshot/ab_test/posted rows
        (they use .add(), not upsert), so only run it once per real DB file.
        """
        import sqlite3
        if not os.path.exists(sqlite_path):
            print(f"No SQLite file found at {sqlite_path}, nothing to migrate.")
            return

        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row
        migrated = {"videos": 0, "snapshots": 0, "ab_tests": 0, "posted": 0, "spy_cache": 0}

        for row in conn.execute("SELECT * FROM videos"):
            self.upsert_video(row["video_id"], row["title"], row["published"], row["channel"])
            migrated["videos"] += 1

        for row in conn.execute("SELECT * FROM snapshots"):
            self.add_snapshot(row["video_id"], row["views"], row["likes"],
                               row["comments"], row["timestamp"])
            migrated["snapshots"] += 1

        for row in conn.execute("SELECT * FROM ab_title_tests"):
            new_id = self.log_ab_test(
                row["topic"], row["winner_title"], row["winner_pattern"],
                row["winner_score"], json.loads(row["all_variations"] or "[]"),
                row["generated_at"],
            )
            if row["video_id"]:
                self.client.collection("ab_title_tests").document(new_id).update({
                    "video_id": row["video_id"]
                })
            if row["actual_views"] is not None:
                self.client.collection("ab_title_tests").document(new_id).update({
                    "actual_views": row["actual_views"]
                })
            migrated["ab_tests"] += 1

        for row in conn.execute("SELECT * FROM posted_topics"):
            self.mark_posted(row["topic"], row["channel"], row["posted_at"])
            migrated["posted"] += 1

        for row in conn.execute("SELECT * FROM spy_cache"):
            self.client.collection("spy_cache").add({
                "channel": row["channel"], "topics": row["topics"], "cached_at": row["cached_at"]
            })
            migrated["spy_cache"] += 1

        conn.close()
        print(f"✅ Migrated to Firestore: {migrated}")
        return migrated

    def migrate_from_json(self, view_history_path="output/view_history.json",
                          ab_log_path="output/title_ab_log.json",
                          posted_path="output/posted_topics.txt"):
        """
        No-op under Firestore. This existed under SQLite because Railway/
        Render's disk wasn't reliably persistent, so scheduler.py restored
        JSON backups from GitHub and rebuilt the DB on every startup.
        Firestore is persistent by default, so that whole restore dance is
        gone — this stub just keeps scheduler.py from crashing until we
        remove the call to it in the Cloud Run Job refactor.
        """
        return {"videos": 0, "snapshots": 0, "ab_tests": 0, "posted": 0}

    # ── Locks (replaces the local generation.lock file) ────────────────────

    def try_acquire_lock(self, name, ttl_seconds=1800):
        """
        Best-effort distributed lock so two overlapping Cloud Run Job
        executions (e.g. Cloud Scheduler retry landing while a slow run is
        still going) don't generate the same video twice. Not perfectly
        atomic (no transaction), but matches the local-file lock's original
        guarantees — good enough for this use case.
        Returns (acquired: bool, age_seconds_of_existing_lock: float).
        """
        ref = self.client.collection("locks").document(name)
        doc = ref.get()
        now = datetime.now(timezone.utc)
        if doc.exists:
            locked_at = datetime.fromisoformat(doc.to_dict()["locked_at"])
            age = (now - locked_at).total_seconds()
            if age < ttl_seconds:
                return False, age
        ref.set({"locked_at": now.isoformat()})
        return True, 0.0

    def release_lock(self, name):
        self.client.collection("locks").document(name).delete()

    # ── Public stats ─────────────────────────────────────────────────────

    def get_public_stats(self):
        """Lightweight counts for app.py's public portfolio page."""
        video_ids = set()
        total_snapshots = 0
        for doc in self.client.collection_group("snapshots").stream():
            total_snapshots += 1
            video_ids.add(doc.to_dict().get("video_id"))
        return {
            "total_videos": len(video_ids),
            "total_snapshots": total_snapshots,
            "db_available": True,
        }

    # ── Analytics (unchanged logic — just reads via get_all_snapshots) ─────


    def get_peak_hours(self, channel=None):
        all_data = self.get_all_snapshots()
        from collections import defaultdict
        hour_velocities = defaultdict(list)

        for video_id, data in all_data.items():
            snapshots = data["snapshots"]
            if len(snapshots) < 2:
                continue
            for i in range(1, len(snapshots)):
                prev = snapshots[i - 1]
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
                "avg_velocity": round(sum(values) / len(values), 4) if values else 0.0,
                "sample_count": len(values),
            }
        return result

    def get_best_upload_hour(self):
        peak_hours = self.get_peak_hours()
        best = max(peak_hours.items(), key=lambda x: x[1]["avg_velocity"])
        if best[1]["sample_count"] < 3:
            return None
        return best[0]


# Singleton instance
db = Database()
