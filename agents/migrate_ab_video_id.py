"""
migrate_ab_video_id.py — OBSOLETE under Firestore.

Used to run `ALTER TABLE ab_title_tests ADD COLUMN video_id` on the old
SQLite database. Firestore is schemaless and agents/database.py's
log_ab_test() already writes a video_id field (defaulting to None) on
every new row, so there's nothing to migrate. Kept as a no-op so any
leftover cron/manual invocations don't error out.
"""


def migrate():
    print("No-op under Firestore — video_id is already part of every ab_title_tests doc.")


if __name__ == "__main__":
    migrate()
