"""
Public Portfolio Page — AI CarryON
No password gate. Safe to share with recruiters.
This is the app entry point (root URL), so it loads first automatically.
"""

import streamlit as st
import os
from datetime import datetime, timezone
from agents.database import db

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
LIVE_APP_URL = "https://ai-carryon-tqndlmjbcfvtznagmef2ap.streamlit.app"

from agents.dashboard_sync import sync_all_channel_data
_sync_status = sync_all_channel_data()

# ─────────────────────────────────────────────
# Pull safe, read-only stats from Firestore (no secrets, no operational data)
# ─────────────────────────────────────────────

def get_public_stats():
    try:
        return db.get_public_stats()
    except Exception:
        return {"total_videos": None, "total_snapshots": None, "db_available": False}


stats = get_public_stats()

# ─────────────────────────────────────────────
# Styling — dark / bold "architects of the future" theme
# (dark, bold agency-style theme: near-black background, big uppercase
#  headline, orange accent, "story in numbers" stat strip, card sections)
# ─────────────────────────────────────────────

st.markdown("""
<style>
:root {
    --accent: #3b82f6;
    --bg: #0b0b0f;
    --card: rgba(255,255,255,0.03);
    --border: rgba(255,255,255,0.08);
}

/* page background */
.stApp {
    background: var(--bg);
}

/* hero */
.hero {
    padding: 56px 8px 40px 8px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 36px;
}
.eyebrow {
    display: inline-block;
    color: var(--accent);
    font-weight: 700;
    letter-spacing: 3px;
    font-size: 0.78rem;
    text-transform: uppercase;
    margin-bottom: 14px;
}
.hero h1 {
    font-size: 3.2rem;
    font-weight: 800;
    line-height: 1.08;
    letter-spacing: -1px;
    text-transform: uppercase;
    margin: 0 0 18px 0;
}
.hero h1 span {
    color: var(--accent);
}
.hero p {
    font-size: 1.15rem;
    color: rgba(255,255,255,0.72);
    max-width: 780px;
    line-height: 1.55;
}
.hero-badge {
    display: inline-block;
    background: rgba(34,197,94,0.15);
    color: #22c55e;
    border: 1px solid rgba(34,197,94,0.4);
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
    margin-bottom: 18px;
}

/* section labels — small caps eyebrow above each heading */
.section-label {
    color: var(--accent);
    font-weight: 700;
    letter-spacing: 3px;
    font-size: 0.75rem;
    text-transform: uppercase;
    margin-bottom: 6px;
}
.section-title {
    font-size: 1.9rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: -0.5px;
    margin: 0 0 18px 0;
}

/* story-in-numbers stat strip */
.stat-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 32px;
    padding: 28px 8px;
    margin: 8px 0 36px 0;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
}
.stat-num {
    font-size: 3rem;
    font-weight: 800;
    color: var(--accent);
    line-height: 1;
}
.stat-label {
    color: rgba(255,255,255,0.6);
    font-size: 0.9rem;
    margin-top: 6px;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.tech-badge {
    display: inline-block;
    background: rgba(59,130,246,0.12);
    color: #a5c9ff;
    border: 1px solid rgba(59,130,246,0.35);
    padding: 4px 12px;
    border-radius: 6px;
    font-size: 0.82rem;
    margin: 3px;
}
.challenge-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 14px;
    transition: border-color 0.15s ease;
}
.challenge-card:hover {
    border-color: var(--accent);
}
.phase-done {
    color: #22c55e;
    font-weight: 600;
}

/* sticky top nav */
.topnav {
    position: sticky;
    top: 0;
    z-index: 999;
    background: rgba(11,11,15,0.92);
    backdrop-filter: blur(6px);
    border-bottom: 1px solid var(--border);
    margin: -1rem -1rem 0 -1rem;
    padding: 14px 24px;
}
.topnav-inner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
}
.topnav-brand {
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
    font-size: 0.95rem;
}
.topnav-links a {
    color: rgba(255,255,255,0.75);
    text-decoration: none;
    font-weight: 600;
    font-size: 0.82rem;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-left: 22px;
}
.topnav-links a:hover {
    color: var(--accent);
}

/* quote / founder-note block */
.quote-block {
    padding: 32px 28px;
    background: var(--card);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 10px;
    margin-bottom: 36px;
}
.quote-block p {
    font-size: 1.25rem;
    line-height: 1.5;
    font-style: italic;
    margin-bottom: 12px;
}
.quote-block span {
    color: var(--accent);
    font-weight: 700;
    letter-spacing: 1px;
    font-size: 0.85rem;
    text-transform: uppercase;
}

/* 3-card "why" grid */
.why-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 20px;
    margin-bottom: 8px;
}
.why-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 24px 22px;
}
.why-card h4 {
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-size: 1.02rem;
    margin: 0 0 10px 0;
    color: var(--accent);
}
.why-card p {
    color: rgba(255,255,255,0.72);
    font-size: 0.92rem;
    line-height: 1.5;
    margin: 0;
}

/* closing CTA band */
.cta-band {
    text-align: center;
    padding: 48px 20px;
    margin: 12px 0 36px 0;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: linear-gradient(180deg, rgba(59,130,246,0.06), transparent);
}
.cta-band h2 {
    font-size: 2rem;
    font-weight: 800;
    text-transform: uppercase;
    margin: 0 0 10px 0;
}
.cta-band p {
    color: rgba(255,255,255,0.7);
    margin-bottom: 4px;
}

/* footer band */
.footer-band {
    background: rgba(255,255,255,0.02);
    border-top: 1px solid var(--border);
    padding: 36px 8px 8px 8px;
    margin-top: 24px;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Top nav — sticky, anchor links to each section below
# (Streamlit has no true mega-menu; this jumps to in-page sections)
# ─────────────────────────────────────────────

st.markdown("""
<div class="topnav">
  <div class="topnav-inner">
    <span class="topnav-brand">🤖 AI CarryON</span>
    <div class="topnav-links">
      <a href="#overview">Overview</a>
      <a href="#why-it-works">Why It Works</a>
      <a href="#how-it-works">How It Works</a>
      <a href="#architecture">Architecture</a>
      <a href="#timeline">Timeline</a>
      <a href="#challenges">Challenges</a>
      <a href="#contact">Contact</a>
    </div>
  </div>
</div>
<div id="overview"></div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Hero — full-width dark banner, big uppercase headline + CTA row
# ─────────────────────────────────────────────

st.markdown('<div class="hero">', unsafe_allow_html=True)
st.markdown('<div class="eyebrow">Autonomous YouTube Intelligence</div>', unsafe_allow_html=True)
st.markdown('<span class="hero-badge">● Live and running in production</span>', unsafe_allow_html=True)
st.markdown('<h1>Architects of <span>Automated</span> Content</h1>', unsafe_allow_html=True)
st.markdown(
    '<p>AI CarryON researches, writes, voices, edits, and uploads YouTube videos on its own '
    '— then learns from how they perform. Three fully independent channels (English + Hindi + '
    'Cricket), each running its own scheduler, script generation, A/B title testing, and '
    'adaptive upload-time logic, with zero manual intervention after deploy.</p>',
    unsafe_allow_html=True,
)
st.markdown('</div>', unsafe_allow_html=True)

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
# Live stats — "story in numbers" style strip
# ─────────────────────────────────────────────

if stats["db_available"] and stats["total_videos"]:
    videos_val = f'{stats["total_videos"]}+'
    snapshots_val = f'{stats["total_snapshots"]:,}+'
else:
    videos_val = "—"
    snapshots_val = "—"

st.markdown('<div class="section-label">Story in numbers</div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="stat-strip">
    <div>
        <div class="stat-num">{videos_val}</div>
        <div class="stat-label">Videos tracked</div>
    </div>
    <div>
        <div class="stat-num">{snapshots_val}</div>
        <div class="stat-label">Snapshots collected</div>
    </div>
    <div>
        <div class="stat-num">3</div>
        <div class="stat-label">Channels running</div>
    </div>
    <div>
        <div class="stat-num">6</div>
        <div class="stat-label">Pipeline phases shipped</div>
    </div>
</div>
""", unsafe_allow_html=True)

if stats["db_available"] and stats["total_videos"]:
    st.caption("Pulled live from the production database — this is real operational data, not a mockup.")
else:
    st.caption("Live figures load once the production database is reachable.")

st.divider()

# ─────────────────────────────────────────────
# Founder note — quote block
# ─────────────────────────────────────────────

st.markdown("""
<div class="quote-block">
<p>"I wanted to prove an AI pipeline could run a real YouTube operation end to end — not a demo,
a production system that researches, decides, and ships without me in the loop, then gets
measurably better every week from its own data."</p>
<span>Amit Kumar — Builder</span>
</div>
""", unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────
# Why it works — 3-card grid
# ─────────────────────────────────────────────

st.markdown('<div id="why-it-works"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">What Makes It Work</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Why This System</div>', unsafe_allow_html=True)

st.markdown("""
<div class="why-grid">
    <div class="why-card">
        <h4>Adaptive, not scheduled</h4>
        <p>Upload timing is learned from real view-velocity data per channel, not a fixed cron
        job — it waits for the hour the data says will perform best.</p>
    </div>
    <div class="why-card">
        <h4>Data-driven, not guessed</h4>
        <p>Every title, topic, and upload decision is benchmarked against top competing videos
        and scored before it's used, not picked by gut feel.</p>
    </div>
    <div class="why-card">
        <h4>Self-correcting, not static</h4>
        <p>Hourly view snapshots feed back into the same database every channel reads from, so
        the system's own history keeps sharpening its next decision.</p>
    </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────
# What this does
# ─────────────────────────────────────────────

st.markdown('<div id="how-it-works"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">How It Works</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">What This System Actually Does</div>', unsafe_allow_html=True)
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

st.markdown('<div id="architecture"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">Under The Hood</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Architecture</div>', unsafe_allow_html=True)

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
   -> Hourly view snapshot -> Firestore
""", language="text")

t1, t2 = st.columns(2)
with t1:
    st.markdown("**Three independent channels, shared infrastructure:**")
    st.markdown("""
- Separate schedulers, separate learning, separate audiences
- Shared Firestore database, partitioned by collection/`channel` field so English, Hindi, and
  Cricket data never mix
- Cloud Run service (dashboard) + Cloud Run Jobs (per-channel workers), triggered by Cloud Scheduler
""")
with t2:
    st.markdown("**Tech stack:**")
    badges = ["Python", "Streamlit", "Firestore", "Cloud Run", "Groq (LLaMA 3.3-70B)",
              "Gemini", "Sarvam AI", "Edge TTS", "YouTube Data API", "Plotly"]
    st.markdown(" ".join(f'<span class="tech-badge">{b}</span>' for b in badges), unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────
# Phase history
# ─────────────────────────────────────────────

st.markdown('<div id="timeline"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">Progress</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Build Timeline</div>', unsafe_allow_html=True)
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

st.markdown('<div id="challenges"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">The Hard Parts</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Engineering Challenges Solved</div>', unsafe_allow_html=True)
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

st.divider()

# ─────────────────────────────────────────────
# Closing CTA band
# ─────────────────────────────────────────────

st.markdown("""
<div class="cta-band">
    <h2>Want To See It Run Live?</h2>
    <p>Full source, architecture, and build history are public — no gatekeeping.</p>
</div>
""", unsafe_allow_html=True)

cta1, cta2 = st.columns(2)
with cta1:
    st.link_button("💻 Browse the Code", GITHUB_URL, use_container_width=True)
with cta2:
    st.link_button("🔗 Let's Connect on LinkedIn", LINKEDIN_URL, use_container_width=True)

st.divider()

# ─────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────

st.markdown('<div id="contact"></div>', unsafe_allow_html=True)
st.markdown('<div class="footer-band">', unsafe_allow_html=True)
st.markdown('<div class="section-label">Reach Out</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Get In Touch</div>', unsafe_allow_html=True)
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
st.markdown('</div>', unsafe_allow_html=True)
