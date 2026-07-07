"""
migrate_ab_video_id.py — adds video_id column to ab_title_tests
so AB tests can be linked directly to uploaded videos instead of
relying on fragile title-string matching.

Safe to run multiple times.
"""

import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "output/aicarryon.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(ab_title_tests)")
    columns = [row[1] for row in cur.fetchall()]

    if "video_id" not in columns:
        cur.execute("ALTER TABLE ab_title_tests ADD COLUMN video_id TEXT")
        print("Added video_id column.")
    else:
        print("video_id already exists — skipping.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
