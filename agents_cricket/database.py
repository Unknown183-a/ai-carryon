"""
agents_cricket/database.py — Firestore database for the Cricket channel.

Migrated from Postgres (Supabase) to Firestore, so Cricket now lives in the
same Firestore project as English/Hindi instead of a separate Supabase
Postgres database. Method signatures are UNCHANGED, so nothing in
agents_cricket/, app_cricket.py, scheduler_cricket.py, or pages/ needs to
be touched beyond this file.

Kept fully isolated via a cricket_ prefix on every collection name, same
isolation goal the old "cricket_" table prefix served in Postgres:
  - cricket_videos            : doc id = video_id
  - cricket_videos/{id}/snapshots : subcollection, auto id
  - cricket_meta               : doc id = key
  - cricket_posted_matches     : doc id = match_id (gives free idempotency,
                                  replacing the old UNIQUE + ON CONFLICT)

Usage (unchanged):
    from agents_cricket.database import db
    db.mark_posted(match_id)
    already_posted = db.get_all_posted_match_ids()

Requires: google-cloud-firestore
Auth: uses Application Default Credentials — automatic on Cloud Run via the
      service's attached service account. Locally, run:
          gcloud auth application-default login
"""

import json
from datetime import datetime, timezone
from google.cloud import firestore


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


class CricketDatabase:
    def __init__(self, project=None, database=None):
        kwargs = {}
        if project:
            kwargs["project"] = project
        if database:
            kwargs["database"] = database
        self.client = firestore.Client(**kwargs)

    # ── Videos ────────────────────────────────────────────────────────────

    def upsert_video(self, video_id, title, published, match_id=None):
        ref = self.client.collection("cricket_videos").document(video_id)
        data = {
            "video_id": video_id,
            "title": title,
            "published": published,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        # Only set match_id when given, so view_tracker's title/published-only
        # refresh doesn't clobber the match_id set at upload time.
        if match_id is not None:
            data["match_id"] = match_id
        ref.set(data, merge=True)

    def get_all_videos(self):
        docs = (self.client.collection("cricket_videos")
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .stream())
        return [d.to_dict() for d in docs]

    # ── Snapshots ────────────────────────────────────────────────────────
    # Stored as a subcollection under each video doc: cricket_videos/{id}/snapshots

    def add_snapshot(self, video_id, views, likes=0, comments=0, timestamp=None):
        if timestamp is None:
            timestamp = _now_iso()
        video_ref = self.client.collection("cricket_videos").document(video_id)
        if not video_ref.get().exists:
            video_ref.set({"video_id": video_id, "title": "", "published": "",
                           "match_id": None, "created_at": firestore.SERVER_TIMESTAMP})
        video_ref.collection("snapshots").add({
            "video_id": video_id,
            "views": views,
            "likes": likes,
            "comments": comments,
            "timestamp": timestamp,
        })

    def get_snapshots(self, video_id):
        col = self.client.collection("cricket_videos").document(video_id).collection("snapshots")
        docs = col.order_by("timestamp", direction=firestore.Query.ASCENDING).stream()
        return [d.to_dict() for d in docs]

    def get_all_snapshots(self):
        """Return all snapshots grouped by video_id — same shape as
        agents/database.py's get_all_snapshots(), so agents_cricket.velocity_agent
        can reuse the exact same velocity-computation logic as English/Hindi."""
        result = {}
        for video_doc in self.client.collection("cricket_videos").stream():
            video = video_doc.to_dict()
            vid_id = video["video_id"]
            result[vid_id] = {
                "title": video.get("title"),
                "published": video.get("published"),
                "match_id": video.get("match_id"),
                "snapshots": self.get_snapshots(vid_id),
            }
        return result

    # ── Meta (key/value, used to throttle YouTube API calls) ──────────────

    def get_meta(self, key):
        doc = self.client.collection("cricket_meta").document(key).get()
        return doc.to_dict()["value"] if doc.exists else None

    def set_meta(self, key, value):
        self.client.collection("cricket_meta").document(key).set({"value": value})

    # ── Posted Matches ──────────────────────────────────────────────────────

    def mark_posted(self, match_id, match_name="", posted_at=None):
        if posted_at is None:
            posted_at = _now_iso()
        ref = self.client.collection("cricket_posted_matches").document(match_id)
        # Using match_id as the doc id gives idempotency for free — same
        # guarantee the old UNIQUE + ON CONFLICT DO NOTHING gave us.
        if not ref.get().exists:
            ref.set({
                "match_id": match_id,
                "match_name": match_name,
                "posted_at": posted_at,
            })

    def is_posted(self, match_id):
        return self.client.collection("cricket_posted_matches").document(match_id).get().exists

    def get_all_posted_match_ids(self):
        docs = self.client.collection("cricket_posted_matches").stream()
        return {d.id for d in docs}

    # ── Migration from Supabase Postgres (run once, from your MacBook) ─────

    def migrate_from_supabase(self, database_url):
        """
        One-time backfill: connects to your existing Supabase Postgres DB
        and writes every row into Firestore. Run this locally BEFORE
        cutting scheduler_cricket.py over — otherwise get_all_posted_match_ids()
        comes back empty and already-covered matches can get reposted.
        Safe to re-run: mark_posted uses match_id as the doc id, so reruns
        just overwrite the same docs rather than duplicating them; add_snapshot
        still uses .add(), so only run this once per real Supabase DB.

        Requires psycopg2-binary installed locally for this one call only —
        it's no longer a runtime dependency, so: pip install psycopg2-binary
        """
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
        migrated = {"videos": 0, "snapshots": 0, "posted": 0, "meta": 0}

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cricket_videos")
            for row in cur.fetchall():
                self.upsert_video(row["video_id"], row["title"], row["published"], row["match_id"])
                migrated["videos"] += 1

            cur.execute("SELECT * FROM cricket_snapshots")
            for row in cur.fetchall():
                self.add_snapshot(row["video_id"], row["views"], row["likes"],
                                   row["comments"], row["timestamp"])
                migrated["snapshots"] += 1

            cur.execute("SELECT * FROM cricket_posted_matches")
            for row in cur.fetchall():
                self.mark_posted(row["match_id"], row["match_name"], row["posted_at"])
                migrated["posted"] += 1

            cur.execute("SELECT * FROM cricket_meta")
            for row in cur.fetchall():
                self.set_meta(row["key"], row["value"])
                migrated["meta"] += 1

        conn.close()
        print(f"✅ Migrated to Firestore: {migrated}")
        return migrated


# Singleton instance — same pattern as agents/database.py's `db`.
# Wrapped in try/except: ADC may not be configured in every local shell,
# and callers (velocity_agent, dashboard pages) check `db_init_error` and
# show a helpful message rather than the whole page crashing on import.
db_init_error = None
try:
    db = CricketDatabase()
except Exception as e:
    db = None
    db_init_error = str(e)
