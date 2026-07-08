"""
pages/comparison.py — Phase 2 Dashboard: Competitor Comparison Engine
Shows how your videos stack up against top competitors on the same topic.
"""

import sys
import os
import json

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

st.set_page_config(page_title="Comparison · AI CarryON", page_icon="🔍", layout="wide")

from agents.dashboard_sync import sync_all_channel_data
_sync_status = sync_all_channel_data()


APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
if APP_PASSWORD:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if pwd == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Wrong password")
        st.stop()

st.title("🔍 Competitor Comparison")
st.caption("See how your videos stack up against top competitors on any topic.")

# ── Channel selector ───────────────────────────────────────────────────────

channel = st.radio(
    "Channel",
    ["AI CarryON (English)", "Hindi AI CarryON"],
    horizontal=True,
)

# ── Topic input ────────────────────────────────────────────────────────────

topic = st.text_input(
    "Topic to analyse",
    placeholder="e.g. Claude 4 Opus benchmark, ChatGPT vs Gemini",
)

run = st.button("🔍 Run Comparison", type="primary")

if not run or not topic.strip():
    st.info("Enter a topic and click Run Comparison.")
    st.stop()

# ── Run comparison ─────────────────────────────────────────────────────────

with st.spinner(f"Fetching competitor data for '{topic}'…"):
    try:
        if channel == "AI CarryON (English)":
            from agents.comparison_agent import compare_topic
            result = compare_topic(topic.strip())
        else:
            from agents_hindi.comparison_agent import compare_topic_hindi
            result = compare_topic_hindi(topic.strip())
    except Exception as e:
        st.error(f"Error running comparison: {e}")
        st.stop()

if "error" in result:
    st.error(f"Comparison failed: {result['error']}")
    st.stop()

competitors  = result.get("competitors", [])
your_video   = result.get("your_video", {})
insights     = result.get("insights", {})

if not competitors:
    st.warning("No competitor data found for this topic in the last 7 days. Try a broader topic.")
    st.stop()

# ── Top metrics ────────────────────────────────────────────────────────────

st.divider()
st.subheader("📊 Benchmark Summary")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Competitors found", len(competitors))
col2.metric("Avg competitor views", f"{insights.get('competitor_avg_views', 0):,}")
col3.metric("Avg engagement rate", f"{insights.get('competitor_avg_engagement', 0):.2f}%")
col4.metric(
    "Best upload hour (UTC)",
    f"{insights.get('best_upload_hour_utc', '—'):02d}:00"
    if insights.get("best_upload_hour_utc") is not None else "—"
)

# Your video vs avg
if your_video:
    st.divider()
    st.subheader("🎯 Your Video vs Competitor Average")
    y1, y2, y3 = st.columns(3)
    view_delta = your_video.get("views", 0) - insights.get("competitor_avg_views", 0)
    y1.metric("Your views", f"{your_video.get('views', 0):,}",
              delta=f"{view_delta:+,}", delta_color="normal")
    eng_delta = your_video.get("engagement_rate", 0) - insights.get("competitor_avg_engagement", 0)
    y2.metric("Your engagement", f"{your_video.get('engagement_rate', 0):.2f}%",
              delta=f"{eng_delta:+.2f}%", delta_color="normal")
    dur_delta = your_video.get("duration_seconds", 0) - insights.get("competitor_avg_duration_seconds", 0)
    y3.metric("Your duration", f"{your_video.get('duration_seconds', 0)}s",
              delta=f"{dur_delta:+}s", delta_color="off")

st.divider()

# ── Views bar chart ────────────────────────────────────────────────────────

st.subheader("📈 Views comparison")

titles     = [c["title"][:40] + "…" if len(c["title"]) > 40 else c["title"] for c in competitors]
views      = [c["views"] for c in competitors]
channels   = [c["channel"] for c in competitors]
colors     = ["#6366f1"] * len(competitors)

if your_video:
    titles.append("▶ YOUR VIDEO")
    views.append(your_video.get("views", 0))
    channels.append("You")
    colors.append("#f59e0b")

fig = go.Figure(go.Bar(
    x=views,
    y=titles,
    orientation="h",
    marker_color=colors,
    hovertemplate="<b>%{y}</b><br>Views: %{x:,}<extra></extra>",
))
fig.update_layout(
    plot_bgcolor="#0f172a",
    paper_bgcolor="#0f172a",
    font_color="#e2e8f0",
    margin=dict(t=10, b=40, l=20, r=20),
    height=400,
    xaxis_title="Views",
    yaxis=dict(autorange="reversed"),
    showlegend=False,
)
st.plotly_chart(fig, use_container_width=True)

# ── Engagement scatter ─────────────────────────────────────────────────────

st.subheader("💬 Engagement rate vs Views")

fig2 = go.Figure()

fig2.add_trace(go.Scatter(
    x=[c["views"] for c in competitors],
    y=[c["engagement_rate"] for c in competitors],
    mode="markers+text",
    text=[c["channel"] for c in competitors],
    textposition="top center",
    marker=dict(size=10, color="#6366f1"),
    name="Competitors",
    hovertemplate="<b>%{text}</b><br>Views: %{x:,}<br>Engagement: %{y:.2f}%<extra></extra>",
))

if your_video:
    fig2.add_trace(go.Scatter(
        x=[your_video.get("views", 0)],
        y=[your_video.get("engagement_rate", 0)],
        mode="markers+text",
        text=["YOU"],
        textposition="top center",
        marker=dict(size=14, color="#f59e0b", symbol="star"),
        name="Your video",
    ))

fig2.update_layout(
    plot_bgcolor="#0f172a",
    paper_bgcolor="#0f172a",
    font_color="#e2e8f0",
    margin=dict(t=10, b=40, l=50, r=20),
    height=350,
    xaxis_title="Views",
    yaxis_title="Engagement rate (%)",
)
st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── Recommendations ────────────────────────────────────────────────────────

st.subheader("💡 Recommendations")

recs = insights.get("recommendations", [])
if recs:
    for rec in recs:
        st.markdown(f"- {rec}")
else:
    st.success("Your video is performing well against competitors!")

# Top competitor callout
st.divider()
st.subheader("🏆 Top competitor")
tc_title = insights.get("top_competitor_title", "")
tc_views = insights.get("top_competitor_views", 0)
tc_url   = insights.get("top_competitor_url", "")
if tc_title:
    st.markdown(f"**[{tc_title}]({tc_url})** — {tc_views:,} views")

st.divider()

# ── Full competitor table ──────────────────────────────────────────────────

st.subheader("Full competitor breakdown")

df = pd.DataFrame(competitors)
df["title"] = df.apply(
    lambda r: f"[{r['title'][:50]}]({r['url']})", axis=1
)
df["duration"] = df["duration_seconds"].apply(lambda s: f"{s//60}m {s%60}s")
df["upload_hour"] = df["upload_hour_utc"].apply(
    lambda h: f"{h:02d}:00 UTC" if h is not None else "—"
)
df = df[["title", "channel", "views", "likes", "engagement_rate", "duration", "upload_hour", "published"]]
df.columns = ["Title", "Channel", "Views", "Likes", "Engagement %", "Duration", "Upload Hour", "Published"]
df.index = range(1, len(df) + 1)

st.dataframe(df, use_container_width=True)

st.caption(f"Topic: '{topic}' · {result.get('checked_at', '')} · Last 7 days")
