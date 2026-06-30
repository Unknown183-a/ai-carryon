"""
pages/peak_hours.py — Phase 1 Dashboard: Velocity Analysis & Peak Upload Windows
Reads from SQLite (primary) — works for both English and Hindi channels.
"""

import sys
import os

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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

st.title("⚡ Peak Hours")
st.caption("View velocity analysis — when your channel gets the most traction.")

# ── Channel selector ────────────────────────────────────────────────────────

channel = st.radio("Channel", ["AI CarryON (English)", "Hindi AI CarryON"], horizontal=True)
is_hindi = channel == "Hindi AI CarryON"

# ── Load analysis from SQLite ───────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_analysis(hindi: bool):
    try:
        if hindi:
            from agents_hindi.velocity_agent import load_and_analyse_hindi
            return load_and_analyse_hindi()
        else:
            from agents.velocity_agent import load_and_analyse
            return load_and_analyse("output/view_history.json")
    except Exception as e:
        return {"error": str(e)}

with st.spinner("Loading velocity data…"):
    analysis = load_analysis(is_hindi)

if "error" in analysis:
    st.error(f"Could not load data: {analysis['error']}")
    st.stop()

if analysis["total_velocity_points"] < 10:
    st.warning(
        f"Only {analysis['total_velocity_points']} data points so far for {channel}. "
        "Need more hourly snapshots. Come back in a day or two."
    )

peak_hours    = analysis["peak_hours"]
best_windows  = analysis["best_upload_windows"]
video_summary = analysis.get("video_summary", [])

# Build video_summary from velocity_data if not present (Hindi path)
if not video_summary and "velocity_data" in analysis:
    video_summary = sorted([
        {
            "video_id": vid,
            "title": v["title"],
            "published": v["published"],
            "avg_velocity": v["avg_velocity"],
            "peak_velocity": v["peak_velocity"],
            "total_snapshots": v["total_snapshots"],
        }
        for vid, v in analysis["velocity_data"].items()
    ], key=lambda x: x["avg_velocity"], reverse=True)

best_hour     = best_windows[0]["hour"]     if best_windows else None
best_velocity = best_windows[0]["avg_velocity"] if best_windows else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Videos analysed",    analysis["total_videos_analysed"])
col2.metric("Velocity data points", analysis["total_velocity_points"])
col3.metric("Best upload hour (UTC)", f"{best_hour:02d}:00" if best_hour is not None else "—")
col4.metric("Peak avg velocity",  f"{best_velocity:.1f} v/hr")

st.divider()

# ── 24h bar chart ──────────────────────────────────────────────────────────

st.subheader(f"Average view velocity by hour of day (UTC) — {channel}")

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
else:
    st.info("No upload windows yet — need more snapshot data.")

st.divider()

# ── Per-video sparkline ────────────────────────────────────────────────────

st.subheader("Video velocity over time")
velocity_data = analysis.get("velocity_data", {})

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
else:
    st.info("No video velocity data yet.")

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
else:
    st.info("No ranked videos yet.")

st.caption(
    f"Channel: {channel} · Data refreshes every 5 min · Loaded from SQLite · "
    f"Last computed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
)
