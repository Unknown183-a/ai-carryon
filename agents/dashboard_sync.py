"""
agents/dashboard_sync.py — OBSOLETE under Firestore.

Used to exist because the dashboard and each scheduler ran as separate
Railway containers with separate filesystems, so scheduler-written SQLite
data had to be relayed through GitHub branches for the dashboard to see it.

Firestore is a single shared, always-live database — the dashboard
(Cloud Run service) and both workers (Cloud Run Jobs) all read/write the
same data directly, with no relay step and no staleness window.

Kept as a no-op (rather than removed) so the 7 existing call sites
(app.py + 6 dashboard pages) don't need to be edited.
"""

import streamlit as st


@st.cache_resource(ttl=300)
def sync_all_channel_data():
    return {
        "english_json": True,
        "english_db": True,
        "hindi_db": True,
        "merge_error": None,
        "note": "no-op — Firestore is shared live, no sync needed",
    }
