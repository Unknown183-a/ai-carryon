"""
pages/peak_hours.py — Phase 1 Dashboard: Velocity Analysis & Peak Upload Windows

Drop this file into your pages/ folder. Streamlit will automatically add it
to the sidebar as "Peak Hours".

Reads output/view_history.json (same file the view tracker writes to).
All computation is handled by agents/velocity_agent.py — no extra dependencies.
"""

import sys
import os

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# Allow imports from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agents.velocity_agent import load_and_analyse

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="Peak Hours · AI CarryON",
    page_icon="⚡",
    layout="wide",
)

# ─────────────────────────────────────────────
# Auth (same pattern as your other pages)
# ─────────────────────────────────────────────

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

# ─────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────

VIEW_HISTORY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "output", "view_history.json"
)

@st.cache_data(ttl=300)  # refresh every 5 min
def load_analysis():
    return load_and_analyse(VIEW_HISTORY_PATH)


st.title("⚡ Peak Hours")
st.caption("View velocity analysis — when your channel gets the most traction.")

with st.spinner("Crunching velocity data…"):
    analysis = load_analysis()

if "error" in analysis:
    st.error(f"Could not load view history: {analysis['error']}")
    st.info("Make sure `output/view_history.json` exists and the view tracker has been running for at least a few hours.")
    st.stop()

if analysis["total_velocity_points"] < 10:
    st.warning(
        f"Only {analysis['total_velocity_points']} data points so far. "
        "Phase 1 needs 48–72 hourly snapshots per video for reliable peak hour detection. "
        "Come back in a day or two."
    )

# ─────────────────────────────────────────────
# Top metrics
# ─────────────────────────────────────────────

peak_hours = analysis["peak_hours"]
best_windows = analysis["best_upload_windows"]
video_summary = analysis["video_summary"]

best_hour = best_windows[0]["hour"] if best_windows else None
best_velocity = best_windows[0]["avg_velocity"] if best_windows else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Videos analysed", analysis["total_videos_analysed"])
col2.metric("Velocity data points", analysis["total_velocity_points"])
col3.metric(
    "Best upload hour (UTC)",
    f"{best_hour:02d}:00" if best_hour is not None else "—",
)
col4.metric("Peak avg velocity", f"{best_velocity:.1f} v/hr")

st.divider()

# ─────────────────────────────────────────────
# Peak hour bar chart (24h)
# ─────────────────────────────────────────────

st.subheader("Average view velocity by hour of day (UTC)")

hours = list(range(24))
avg_velocities = [peak_hours[h]["avg_velocity"] for h in hours]
sample_counts  = [peak_hours[h]["sample_count"]  for h in hours]
hour_labels    = [f"{h:02d}:00" for h in hours]

# Colour: highlight the top 5 windows
top_hour_set = {w["hour"] for w in best_windows}
bar_colors = [
    "#6366f1" if h in top_hour_set else "#334155"
    for h in hours
]

fig_peak = go.Figure(
    go.Bar(
        x=hour_labels,
        y=avg_velocities,
        marker_color=bar_colors,
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Avg velocity: %{y:.1f} views/hr<br>"
            "Sample count: %{customdata}<extra></extra>"
        ),
        customdata=sample_counts,
        name="Avg velocity",
    )
)

fig_peak.update_layout(
    xaxis_title="Hour of day (UTC)",
    yaxis_title="Avg views per hour",
    plot_bgcolor="#0f172a",
    paper_bgcolor="#0f172a",
    font_color="#e2e8f0",
    xaxis=dict(tickfont=dict(size=11)),
    margin=dict(t=20, b=40, l=50, r=20),
    height=340,
    showlegend=False,
)

# Shade the top-5 windows
for w in best_windows:
    fig_peak.add_vrect(
        x0=w["hour"] - 0.5,
        x1=w["hour"] + 0.5,
        fillcolor="rgba(99,102,241,0.12)",
        line_width=0,
    )

st.plotly_chart(fig_peak, use_container_width=True)

# ─────────────────────────────────────────────
# Best upload windows table
# ─────────────────────────────────────────────

st.subheader("🏆 Top 5 upload windows")

windows_df = pd.DataFrame(best_windows)
windows_df["hour_label"] = windows_df["hour"].apply(lambda h: f"{h:02d}:00 UTC")
windows_df["avg_velocity"] = windows_df["avg_velocity"].apply(lambda v: f"{v:.1f} v/hr")
windows_df["sample_count"] = windows_df["sample_count"].apply(lambda n: f"{n} snapshots")
windows_df = windows_df[["hour_label", "avg_velocity", "sample_count"]]
windows_df.columns = ["Upload hour (UTC)", "Avg velocity", "Data points"]
windows_df.index = ["🥇", "🥈", "🥉", "4th", "5th"][: len(windows_df)]

st.dataframe(windows_df, use_container_width=True)

st.divider()

# ─────────────────────────────────────────────
# Per-video velocity sparklines
# ─────────────────────────────────────────────

st.subheader("Video velocity over time")

velocity_data = analysis["velocity_data"]

if not velocity_data:
    st.info("No velocity data yet.")
else:
    # Selector
    video_options = {
        f"{v['title'][:55]}…" if len(v['title']) > 55 else v['title']: vid_id
        for vid_id, v in velocity_data.items()
    }
    selected_title = st.selectbox("Select a video", list(video_options.keys()))
    selected_id    = video_options[selected_title]
    vdata          = velocity_data[selected_id]

    points = vdata["velocity_points"]
    df_v   = pd.DataFrame(points)
    df_v["timestamp"] = pd.to_datetime(df_v["timestamp"])

    col_a, col_b = st.columns([2, 1])

    with col_a:
        fig_v = px.area(
            df_v,
            x="timestamp",
            y="velocity",
            labels={"velocity": "Views / hr", "timestamp": ""},
            color_discrete_sequence=["#6366f1"],
        )
        fig_v.update_layout(
            plot_bgcolor="#0f172a",
            paper_bgcolor="#0f172a",
            font_color="#e2e8f0",
            margin=dict(t=10, b=30, l=50, r=20),
            height=260,
        )
        fig_v.update_traces(fillcolor="rgba(99,102,241,0.15)", line_width=2)
        st.plotly_chart(fig_v, use_container_width=True)

    with col_b:
        st.metric("Avg velocity", f"{vdata['avg_velocity']:.1f} v/hr")
        st.metric("Peak velocity", f"{vdata['peak_velocity']:.1f} v/hr")
        st.metric("Snapshots", vdata["total_snapshots"])
        if vdata["published"]:
            st.caption(f"Published: {vdata['published']}")

st.divider()

# ─────────────────────────────────────────────
# Full video ranking table
# ─────────────────────────────────────────────

st.subheader("All videos — velocity ranking")

if video_summary:
    df_rank = pd.DataFrame(video_summary)
    df_rank["avg_velocity"]  = df_rank["avg_velocity"].apply(lambda v: f"{v:.1f}")
    df_rank["peak_velocity"] = df_rank["peak_velocity"].apply(lambda v: f"{v:.1f}")
    df_rank = df_rank[["title", "published", "avg_velocity", "peak_velocity", "total_snapshots"]]
    df_rank.columns = ["Title", "Published", "Avg v/hr", "Peak v/hr", "Snapshots"]
    df_rank.index = range(1, len(df_rank) + 1)
    st.dataframe(df_rank, use_container_width=True)
else:
    st.info("No ranked data yet.")

# ─────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────

st.caption(
    f"Data refreshes every 5 minutes · Powered by `velocity_agent.py` · "
    f"Last computed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
)
