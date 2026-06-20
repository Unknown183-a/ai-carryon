"""
pages/peak_hours.py — Phase 1 Dashboard: Velocity Analysis & Peak Upload Windows
Loads view_history.json from GitHub data branch (works across Railway services).
"""

import sys
import os
import json
import requests

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agents.velocity_agent import (
    compute_velocity,
    get_peak_hours,
    get_best_upload_windows,
    get_video_velocity_summary,
)

st.set_page_config(page_title="Peak Hours · AI CarryON", page_icon="⚡", layout="wide")

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

# ── Load view_history from GitHub data branch ──────────────────────────────

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "Unknown183-a/ai-carryon")

@st.cache_data(ttl=300)
def load_view_history_from_github():
    if not GITHUB_TOKEN:
        return None, "GITHUB_TOKEN not set"

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/output/view_history.json?ref=data"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.raw",
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return json.loads(r.text), None
        else:
            return None, f"GitHub returned {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=300)
def load_analysis():
    view_history, err = load_view_history_from_github()
    if err:
        return {"error": err}

    velocity_data  = compute_velocity(view_history)
    peak_hours     = get_peak_hours(view_history)
    best_windows   = get_best_upload_windows(view_history, top_n=5)
    video_summary  = get_video_velocity_summary(view_history)
    total_points   = sum(len(v["velocity_points"]) for v in velocity_data.values())

    return {
        "velocity_data": velocity_data,
        "peak_hours": peak_hours,
        "best_upload_windows": best_windows,
        "video_summary": video_summary,
        "total_videos_analysed": len(velocity_data),
        "total_velocity_points": total_points,
    }


st.title("⚡ Peak Hours")
st.caption("View velocity analysis — when your channel gets the most traction.")

with st.spinner("Loading from GitHub…"):
    analysis = load_analysis()

if "error" in analysis:
    st.error(f"Could not load view history: {analysis['error']}")
    st.stop()

if analysis["total_velocity_points"] < 10:
    st.warning(
        f"Only {analysis['total_velocity_points']} data points so far. "
        "Need 48–72 hourly snapshots per video. Come back tomorrow."
    )

peak_hours    = analysis["peak_hours"]
best_windows  = analysis["best_upload_windows"]
video_summary = analysis["video_summary"]

best_hour     = best_windows[0]["hour"]     if best_windows else None
best_velocity = best_windows[0]["avg_velocity"] if best_windows else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Videos analysed",    analysis["total_videos_analysed"])
col2.metric("Velocity data points", analysis["total_velocity_points"])
col3.metric("Best upload hour (UTC)", f"{best_hour:02d}:00" if best_hour is not None else "—")
col4.metric("Peak avg velocity",  f"{best_velocity:.1f} v/hr")

st.divider()

# ── 24h bar chart ──────────────────────────────────────────────────────────

st.subheader("Average view velocity by hour of day (UTC)")

hours         = list(range(24))
avg_velocities = [peak_hours[h]["avg_velocity"] for h in hours]
sample_counts  = [peak_hours[h]["sample_count"]  for h in hours]
hour_labels    = [f"{h:02d}:00" for h in hours]
top_hour_set   = {w["hour"] for w in best_windows}
bar_colors     = ["#6366f1" if h in top_hour_set else "#334155" for h in hours]

fig_peak = go.Figure(go.Bar(
    x=hour_labels, y=avg_velocities,
    marker_color=bar_colors,
    hovertemplate="<b>%{x}</b><br>Avg velocity: %{y:.1f} views/hr<br>Samples: %{customdata}<extra></extra>",
    customdata=sample_counts,
))
fig_peak.update_layout(
    xaxis_title="Hour of day (UTC)", yaxis_title="Avg views per hour",
    plot_bgcolor="#0f172a", paper_bgcolor="#0f172a", font_color="#e2e8f0",
    margin=dict(t=20, b=40, l=50, r=20), height=340, showlegend=False,
)
for w in best_windows:
    fig_peak.add_vrect(x0=w["hour"]-0.5, x1=w["hour"]+0.5,
                       fillcolor="rgba(99,102,241,0.12)", line_width=0)

st.plotly_chart(fig_peak, use_container_width=True)

# ── Best windows table ─────────────────────────────────────────────────────

st.subheader("🏆 Top 5 upload windows")
if best_windows:
    df_w = pd.DataFrame(best_windows)
    df_w["hour_label"]    = df_w["hour"].apply(lambda h: f"{h:02d}:00 UTC")
    df_w["avg_velocity"]  = df_w["avg_velocity"].apply(lambda v: f"{v:.1f} v/hr")
    df_w["sample_count"]  = df_w["sample_count"].apply(lambda n: f"{n} snapshots")
    df_w = df_w[["hour_label", "avg_velocity", "sample_count"]]
    df_w.columns = ["Upload hour (UTC)", "Avg velocity", "Data points"]
    df_w.index = ["🥇","🥈","🥉","4th","5th"][:len(df_w)]
    st.dataframe(df_w, use_container_width=True)

st.divider()

# ── Per-video sparkline ────────────────────────────────────────────────────

st.subheader("Video velocity over time")
velocity_data = analysis["velocity_data"]

if velocity_data:
    video_options = {
        (v["title"][:55] + "…" if len(v["title"]) > 55 else v["title"]): vid_id
        for vid_id, v in velocity_data.items()
    }
    selected_title = st.selectbox("Select a video", list(video_options.keys()))
    selected_id    = video_options[selected_title]
    vdata          = velocity_data[selected_id]

    df_v = pd.DataFrame(vdata["velocity_points"])
    df_v["timestamp"] = pd.to_datetime(df_v["timestamp"])

    col_a, col_b = st.columns([2, 1])
    with col_a:
        fig_v = px.area(df_v, x="timestamp", y="velocity",
                        labels={"velocity": "Views / hr", "timestamp": ""},
                        color_discrete_sequence=["#6366f1"])
        fig_v.update_layout(plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
                            font_color="#e2e8f0",
                            margin=dict(t=10, b=30, l=50, r=20), height=260)
        fig_v.update_traces(fillcolor="rgba(99,102,241,0.15)", line_width=2)
        st.plotly_chart(fig_v, use_container_width=True)
    with col_b:
        st.metric("Avg velocity",  f"{vdata['avg_velocity']:.1f} v/hr")
        st.metric("Peak velocity", f"{vdata['peak_velocity']:.1f} v/hr")
        st.metric("Snapshots",     vdata["total_snapshots"])
        if vdata["published"]:
            st.caption(f"Published: {vdata['published']}")

st.divider()

# ── Full ranking table ─────────────────────────────────────────────────────

st.subheader("All videos — velocity ranking")
if video_summary:
    df_rank = pd.DataFrame(video_summary)
    df_rank["avg_velocity"]  = df_rank["avg_velocity"].apply(lambda v: f"{v:.1f}")
    df_rank["peak_velocity"] = df_rank["peak_velocity"].apply(lambda v: f"{v:.1f}")
    df_rank = df_rank[["title","published","avg_velocity","peak_velocity","total_snapshots"]]
    df_rank.columns = ["Title","Published","Avg v/hr","Peak v/hr","Snapshots"]
    df_rank.index = range(1, len(df_rank)+1)
    st.dataframe(df_rank, use_container_width=True)

st.caption(
    f"Data refreshes every 5 min · Loaded from GitHub data branch · "
    f"Last computed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
)
