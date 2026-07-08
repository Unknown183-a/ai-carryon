"""
agents/dashboard_sync.py — keeps the dashboard's local filesystem in sync
with GitHub-backed production data.

The dashboard (`ai-carryon` Railway service) and the schedulers (`worker`
services, one per channel) run as separate containers with separate
filesystems. Nothing written by a scheduler is visible to the dashboard
unless it's pulled in explicitly — this module does that pull, once per
cached window, from both GitHub branches:

    data        -> English's view_history.json + aicarryon.db
    data-hindi  -> Hindi's aicarryon.db

English's SQLite data becomes the local aicarryon.db directly. Hindi's is
downloaded to a temp file and merged in (INSERT OR IGNORE against dedupe
indexes), since both channels share the same schema but live in separate
GitHub branches with no natural way to combine them upstream.

Call sync_all_channel_data() at the top of every Streamlit page that reads
local files or the local DB. It's cached (5 min TTL) so calling it from
multiple pages in the same session is cheap after the first hit.
"""

import os
import sqlite3
import streamlit as st

from agents.data_persistence import restore_sqlite_db, restore_view_history, DB_FILE

HINDI_DB_TEMP = "output/aicarryon_hindi_remote.db"


@st.cache_resource(ttl=300)
def sync_all_channel_data():
    """
    Pulls English + Hindi data from GitHub into local files. Safe to call
    from any page — cached for 5 minutes across the whole dashboard session.
    """
    results = {
        "english_json": False,
        "english_db": False,
        "hindi_db": False,
        "merge_error": None,
    }

    results["english_json"] = restore_view_history()
    results["english_db"] = restore_sqlite_db(branch="data", local_path=DB_FILE)

    hindi_ok = restore_sqlite_db(branch="data-hindi", local_path=HINDI_DB_TEMP)
    results["hindi_db"] = hindi_ok

    if hindi_ok and os.path.exists(HINDI_DB_TEMP):
        try:
            _merge_hindi_into_main(HINDI_DB_TEMP, DB_FILE)
        except Exception as e:
            results["merge_error"] = str(e)

    return results


def _merge_hindi_into_main(hindi_path, main_path):
    """
    Merges Hindi's videos/snapshots/ab_title_tests/posted_topics into the
    local (English-based) aicarryon.db. Idempotent — safe to run every sync
    cycle, since dedupe indexes make repeat merges a no-op for rows already
    present.
    """
    conn = sqlite3.connect(main_path)
    cur = conn.cursor()

    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_dedupe ON snapshots(video_id, timestamp)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ab_dedupe ON ab_title_tests(topic, winner_title, generated_at)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_posted_dedupe ON posted_topics(topic, channel, posted_at)")

    cur.execute(f"ATTACH DATABASE '{hindi_path}' AS hindi_src")

    cur.execute("""
        INSERT OR IGNORE INTO videos (video_id, title, published, channel, created_at)
        SELECT video_id, title, published, channel, created_at FROM hindi_src.videos
    """)
    cur.execute("""
        INSERT OR IGNORE INTO snapshots (video_id, views, likes, comments, timestamp)
        SELECT video_id, views, likes, comments, timestamp FROM hindi_src.snapshots
    """)
    cur.execute("""
        INSERT OR IGNORE INTO ab_title_tests
        (topic, winner_title, winner_pattern, winner_score, all_variations, generated_at,
         actual_views, actual_views_24h, actual_checked_at, video_id)
        SELECT topic, winner_title, winner_pattern, winner_score, all_variations, generated_at,
               actual_views, actual_views_24h, actual_checked_at, video_id
        FROM hindi_src.ab_title_tests
    """)
    cur.execute("""
        INSERT OR IGNORE INTO posted_topics (topic, channel, posted_at)
        SELECT topic, channel, posted_at FROM hindi_src.posted_topics
    """)

    conn.commit()
    cur.execute("DETACH DATABASE hindi_src")
    conn.close()
