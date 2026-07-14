"""
Public Portfolio Page — AI CarryON
No password gate. Safe to share with recruiters.
This is the app entry point (root URL), so it loads first automatically.
"""

import streamlit as st
import sqlite3
import os
from datetime import datetime, timezone

st.set_page_config(
    page_title="AI CarryON — Autonomous YouTube Intelligence System",
    page_icon="🤖",
    layout="wide",
)

# ─────────────────────────────────────────────
# Config — your links
# ─────────────────────────────────────────────

GITHUB_URL = "https://github.com/Unknown183-a/ai-carryon"
LINKEDIN_URL = "https://linkedin.com/in/amit-kumar-731563317"
ENGLISH_CHANNEL_URL = "https://youtube.com/@AIcarryONAI"
HINDI_CHANNEL_URL = "https://youtube.com/@AIcarryONHindi"
CRICKET_CHANNEL_URL = "https://youtube.com/@AIcarryONSports"  # update to your real handle once set
LIVE_APP_URL = "https://ai-carryon-production.up.railway.app"

DB_PATH = os.environ.get("DB_PATH", "output/aicarryon.db")

from agents.dashboard_sync import sync_all_channel_data
_sync_status = sync_all_channel_data()

# ─────────────────────────────────────────────
# Pull safe, read-only stats from SQLite (no secrets, no operational data)
# ─────────────────────────────────────────────

def get_public_stats():
    stats = {
        "total_videos": None,
        "total_snapshots": None,
        "db_available": False,
    }
    try:
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(DISTINCT video_id) FROM snapshots")
            stats["total_videos"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM snapshots")
            stats["total_snapshots"] = cur.fetchone()[0]
            stats["db_available"] = True
            conn.close()
    except Exception:
        pass
    return stats


stats = get_public_stats()

# ─────────────────────────────────────────────
# Styling
# ─────────────────────────────────────────────

st.markdown("""
<style>
.hero-badge {
    display: inline-block;
    background: rgba(34,197,94,0.15);
    color: #22c55e;
    border: 1px solid rgba(34,197,94,0.4);
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
    margin-bottom: 12px;
}
.tech-badge {
    display: inline-block;
    background: rgba(99,102,241,0.15);
    color: #a5b4fc;
    border: 1px solid rgba(99,102,241,0.3);
    padding: 4px 12px;
    border-radius: 6px;
    font-size: 0.82rem;
    margin: 3px;
}
.challenge-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 14px;
}
.phase-done {
    color: #22c55e;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Hero
# ─────────────────────────────────────────────

st.markdown('<span class="hero-badge">● Live and running in production</span>', unsafe_allow_html=True)
st.title("🤖 AI CarryON")
st.subheader("An autonomous system that researches, writes, voices, edits, and uploads YouTube videos — then learns from how they perform.")

st.markdown(
    "Three fully independent channels (English + Hindi + Cricket), each running its own "
    "scheduler, script generation, A/B title testing, and adaptive upload-time logic — "
    "with zero manual intervention after deploy."
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.link_button("🎬 Watch: English Channel", ENGLISH_CHANNEL_URL, use_container_width=True)
with col2:
    st.link_button("🎬 Watch: Hindi Channel", HINDI_CHANNEL_URL, use_container_width=True)
with col3:
    st.link_button("🏏 Watch: Cricket Channel", CRICKET_CHANNEL_URL, use_container_width=True)
with col4:
    st.link_button("💻 View Source on GitHub", GITHUB_URL, use_container_width=True)

st.caption(f"Also live: [{LIVE_APP_URL}]({LIVE_APP_URL}) · [LinkedIn]({LINKEDIN_URL})")

st.divider()

# ─────────────────────────────────────────────
# Live stats (only shown if DB has real data)
# ─────────────────────────────────────────────

if stats["db_available"] and stats["total_videos"]:
    st.markdown("### 📊 Live system stats")
    s1, s2, s3 = st.columns(3)
    s1.metric("Videos tracked", stats["total_videos"])
    s2.metric("Snapshots collected", f"{stats['total_snapshots']:,}")
    s3.metric("Channels running", "2 (English + Hindi)")
    st.caption("Pulled live from the production database — this is real operational data, not a mockup.")
    st.divider()

# ─────────────────────────────────────────────
# What this does
# ─────────────────────────────────────────────

st.markdown("## What this system actually does")
st.markdown("""
Each channel runs an hourly-checking scheduler that, without human input:

1. Checks whether the current hour matches a data-driven peak engagement window (adaptive — falls back to safe defaults until enough data exists)
2. Fetches a trending topic, filtered against the channel's niche
3. Checks topic saturation — skips anything already covered by 20+ recent videos or major authority channels
4. Runs a competitor comparison — pulls the top 10 videos on the same topic and benchmarks views, engagement, and title/length patterns
5. Researches the topic and writes a script, tuned per channel
6. Generates 3 title variations using different psychological patterns (curiosity, urgency, revelation, contrarian, etc.), scores each, and picks a winner
7. Generates SEO description, hashtags, and a thumbnail
8. Generates background visuals (stock footage or cinematic AI clips)
9. Generates voiceover — Edge TTS for English, Sarvam AI native-language voices for Hindi
10. Renders captions and final video
11. Uploads to YouTube with full metadata
12. Records a view snapshot every hour after upload to feed back into the learning loop
""")

st.divider()

# ─────────────────────────────────────────────
# Architecture
# ─────────────────────────────────────────────

st.markdown("## Architecture")

st.code("""
Adaptive Hour Check (Phase 4)
   -> Trending Topic (niche-filtered)
   -> Saturation Check (Phase 1.5)
   -> Competitor Comparison (Phase 2)
   -> Research (Groq LLaMA 3.3-70B, Gemini fallback)
   -> Script (channel-specific length/style)
   -> A/B Title Test (Phase 3) - 3 patterns scored, winner selected
   -> SEO (description, hashtags)
   -> Thumbnail
   -> Background visuals (Pexels auto OR Flow/Veo cinematic clips)
   -> Voiceover (Edge TTS / Sarvam AI)
   -> Render + captions
   -> Upload to YouTube
   -> Hourly view snapshot -> SQLite
""", language="text")

t1, t2 = st.columns(2)
with t1:
    st.markdown("**Two independent channels, shared infrastructure:**")
    st.markdown("""
- Separate schedulers, separate learning, separate audiences
- Shared SQLite database, partitioned by `channel` so English and Hindi data never mix
- Two Railway services (web dashboard + background worker) with a shared persistent volume
""")
with t2:
    st.markdown("**Tech stack:**")
    badges = ["Python", "Streamlit", "SQLite", "Railway", "Groq (LLaMA 3.3-70B)",
              "Gemini", "Sarvam AI", "Edge TTS", "YouTube Data API", "Plotly"]
    st.markdown(" ".join(f'<span class="tech-badge">{b}</span>' for b in badges), unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────
# Phase history
# ─────────────────────────────────────────────

st.markdown("## Build timeline")
phases = [
    ("Phase 0", "Core pipeline — research, script, voice, render, upload"),
    ("Phase 1", "Velocity tracking + Peak Hours dashboard"),
    ("Phase 1.5", "Topic saturation engine — avoid duplicate/oversaturated topics"),
    ("Phase 2", "Competitor comparison — benchmark against top 10 videos per topic"),
    ("Phase 3", "A/B title testing — 3 psychological patterns scored per video"),
    ("Phase 4", "Fully adaptive scheduling — hourly checks, uploads only at data-driven peak windows"),
]
for name, desc in phases:
    st.markdown(f'<span class="phase-done">✅ {name}</span> — {desc}', unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────
# Engineering challenges — the actual resume material
# ─────────────────────────────────────────────

st.markdown("## Engineering challenges solved")
st.caption("This is the part that actually shows debugging depth, not just \"built with AI.\"")

challenges = [
    (
        "Cross-service database architecture bug",
        "The web dashboard and background worker run as separate Railway containers, each with "
        "its own filesystem. Diagnosed why the dashboard showed 'file not found' while the worker "
        "was writing real data — SQLite files don't share disk across containers without an "
        "explicit shared volume."
    ),
    (
        "Silent audio-truncation bug",
        "Hindi voiceovers were losing a portion of generated audio during the WAV-to-MP3 "
        "conversion step in the pipeline — traced it to a format handling gap and fixed the "
        "conversion path so full audio reaches the final render."
    ),
    (
        "JSON-to-SQLite migration with zero data loss",
        "Migrated view-tracking history from a flat JSON file (which was getting wiped on every "
        "Railway redeploy due to the ephemeral filesystem) to a persistent SQLite database, "
        "keeping the JSON file as a fallback loader for backward compatibility."
    ),
    (
        "Stale-cache bug after live fixes",
        "Diagnosed why a confirmed, deployed fix wasn't showing up in the UI — Streamlit's "
        "`@st.cache_data(ttl=300)` was serving a cached error response from before the fix landed. "
        "Added manual refresh controls so cache staleness stops masking real deploy status."
    ),
    (
        "Categorical-axis chart crash in Plotly",
        "A chart on the Schedule dashboard was crashing with a type error caused by mixing an "
        "hour-string label with `add_vline`'s coordinate math on a categorical x-axis. Rebuilt the "
        "'current hour' marker using `add_vrect` against label indices instead."
    ),
    (
        "Credential exposure caught before going public",
        "Found a stray `.env.save` file tracked in git history containing live API keys. Rotated "
        "every credential and used `git filter-repo` to strip the file from all 240+ commits of "
        "history before making the repository public."
    ),
]

for title, desc in challenges:
    st.markdown(f'<div class="challenge-card"><strong>{title}</strong><br>{desc}</div>', unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────

st.markdown("## Get in touch")
f1, f2, f3 = st.columns(3)
with f1:
    st.link_button("🔗 LinkedIn", LINKEDIN_URL, use_container_width=True)
with f2:
    st.link_button("💻 GitHub Repo", GITHUB_URL, use_container_width=True)
with f3:
    st.link_button("🌐 Live Dashboard", LIVE_APP_URL, use_container_width=True)

st.caption(
    "Other pages in the sidebar (Dashboard, Peak Hours, A/B Titles, Schedule, Comparison) are the "
    "operational control panel — password protected."
)

st.info(
    "🔒 **Why the other tabs are locked**\n\n"
    "Those pages include a **live \'Generate & Upload Video\' control** that publishes directly to "
    "both YouTube channels using real API credentials. If left public, anyone visiting this page "
    "could trigger uploads — including abusive, spam, or harmful content — under my channel\'s name. "
    "Keeping that panel behind a password protects the channels and keeps the system\'s real "
    "operational access private, while this Portfolio page stays fully open so you can see the "
    "architecture, the build history, and the engineering work without needing any access."
)
