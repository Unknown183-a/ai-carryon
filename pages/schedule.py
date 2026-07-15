"""
pages/schedule.py — Phase 4 Dashboard: Adaptive Scheduling
Shows optimal upload windows and current schedule recommendation.
Works for both English and Hindi channels via selector.
"""

import sys
import os
from datetime import datetime, timezone

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

st.set_page_config(page_title="Schedule · AI CarryON", page_icon="🕐", layout="wide")

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

st.title("🕐 Adaptive Schedule")
st.caption("Upload at the exact hour your audience is most active.")

# ── Channel selector ────────────────────────────────────────────────────────

channel = st.radio("Channel", ["AI CarryON (English)", "Hindi AI CarryON", "Cricket AI CarryON"], horizontal=True)
is_hindi = channel == "Hindi AI CarryON"
is_cricket = channel == "Cricket AI CarryON"

col_refresh, _ = st.columns([1, 5])
with col_refresh:
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

# ── Load data ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_recommendation(hindi: bool, cricket: bool):
    try:
        if cricket:
            from agents_cricket.velocity_agent import load_and_analyse_cricket, get_best_upload_hour_cricket
            analysis = load_and_analyse_cricket()
            if "error" in analysis:
                return {"error": analysis["error"]}
            best_hour = get_best_upload_hour_cricket()
            windows = analysis["best_upload_windows"]
            peak_hours = analysis["peak_hours"]
            total_points = analysis["total_velocity_points"]
            source = "Cricket Postgres (Supabase)"
        elif hindi:
            from agents_hindi.velocity_agent import load_and_analyse_hindi, get_best_upload_hour_hindi
            analysis = load_and_analyse_hindi()
            best_hour = get_best_upload_hour_hindi()
            windows = analysis["best_upload_windows"]
            peak_hours = analysis["peak_hours"]
            total_points = analysis["total_velocity_points"]
            source = "Hindi SQLite"
        else:
            from agents.adaptive_scheduler import get_schedule_recommendation, get_best_upload_windows, get_peak_hours_analysis
            rec = get_schedule_recommendation()
            windows, _ = get_best_upload_windows(top_n=24)
            peak_hours, source = get_peak_hours_analysis()
            best_hour = rec.get("best_hour")
            total_points = None

        return {
            "best_hour": best_hour,
            "windows": windows,
            "peak_hours": peak_hours,
            "source": source,
            "total_points": total_points,
        }
    except Exception as e:
        return {"error": str(e)}

with st.spinner("Analyzing view velocity data..."):
    data = load_recommendation(is_hindi, is_cricket)

if "error" in data:
    st.error(f"Error: {data['error']}")
    st.stop()

best_hour = data["best_hour"]
top_windows = data["windows"]
peak_hours = data["peak_hours"]
source = data["source"]

if best_hour is None:
    st.warning("⏳ Not enough data yet for this channel. Need more hourly snapshots.")
else:
    st.success(f"✅ Best upload hour identified: {best_hour:02d}:00 UTC")

# ── Top metrics ────────────────────────────────────────────────────────────

now_utc = datetime.now(timezone.utc)
ist_hour = (best_hour + 5) % 24 if best_hour is not None else None

col1, col2, col3, col4 = st.columns(4)
col1.metric("Best upload hour (UTC)", f"{best_hour:02d}:00" if best_hour is not None else "—")
col2.metric("Best upload hour (IST)", f"{ist_hour:02d}:30" if ist_hour is not None else "—")
col3.metric("Current UTC time", now_utc.strftime("%H:%M"))
col4.metric(
    "Recommendation",
    "Upload now ✅" if best_hour == now_utc.hour else
    f"Wait for {best_hour:02d}:00 UTC" if best_hour is not None else "—"
)

st.divider()

# ── 24h velocity chart ─────────────────────────────────────────────────────

_channel_label = "Cricket" if is_cricket else ("Hindi" if is_hindi else "English")
st.subheader(f"📈 {_channel_label} view velocity by hour (UTC)")

try:
    hours = list(range(24))
    velocities = [peak_hours.get(h, {}).get("avg_velocity", 0) for h in hours]
    samples = [peak_hours.get(h, {}).get("sample_count", 0) for h in hours]
    labels = [f"{h:02d}:00" for h in hours]
    top_set = {w["hour"] for w in top_windows[:3]} if top_windows else set()
    colors = ["#6366f1" if h in top_set else "#334155" for h in hours]

    fig = go.Figure(go.Bar(
        x=labels,
        y=velocities,
        marker_color=colors,
        hovertemplate="<b>%{x} UTC</b><br>Avg velocity: %{y:.1f} views/hr<br>Samples: %{customdata}<extra></extra>",
        customdata=samples,
    ))

    now_label = now_utc.strftime("%H:00")
    if now_label in labels:
        now_idx = labels.index(now_label)
        fig.add_vrect(
            x0=now_idx - 0.5,
            x1=now_idx + 0.5,
            fillcolor="rgba(245,158,11,0.15)",
            line_color="#f59e0b",
            line_width=2,
            annotation_text="Now",
            annotation_position="top",
        )

    fig.update_layout(
        plot_bgcolor="#0f172a",
        paper_bgcolor="#0f172a",
        font_color="#e2e8f0",
        margin=dict(t=20, b=40, l=50, r=20),
        height=340,
        xaxis_title="Hour (UTC)",
        yaxis_title="Avg views/hr",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.info(f"Chart not available yet: {e}")

st.divider()

# ── Best windows table ────────────────────────────────────────────────────

if top_windows:
    st.subheader("🏆 Best upload windows")
    rows = []
    for w in top_windows:
        ist = (w["hour"] + 5) % 24
        rows.append({
            "UTC Hour": f"{w['hour']:02d}:00",
            "IST (approx)": f"{ist:02d}:30",
            "Avg views/hr": f"{w['avg_velocity']:.1f}",
            "Data points": w["sample_count"],
        })
    df = pd.DataFrame(rows)
    df.index = (["🥇", "🥈", "🥉"] + [f"{i+4}th" for i in range(len(df) - 3)])[:len(df)]
    st.dataframe(df, use_container_width=True)
else:
    st.info("No upload windows yet — need more snapshot data.")

st.divider()

# ── How it works ──────────────────────────────────────────────────────────

with st.expander("How adaptive scheduling works"):
    st.markdown("""
**Phase 4 logic:**

1. Every hour, the view tracker records how many views each video gained
2. It calculates *velocity* = views gained ÷ hours elapsed for each snapshot pair
3. It groups velocities by the UTC hour they were recorded
4. The hour with the highest average velocity = best upload time

**English, Hindi, and Cricket channels are tracked completely separately** — different audiences,
different timezones, different peak hours. This page shows whichever channel you select above.
Cricket's data lives in its own Supabase Postgres database (Render free tier has no persistent
disk), while English/Hindi share the SQLite database.

**Scheduler behavior:**
- If best hour is within 90 minutes → waits and uploads at that hour
- If best hour is more than 90 minutes away → uploads immediately (doesn't waste time)
- If not enough data yet → uploads immediately

**Why this matters:**
YouTube's algorithm boosts videos hardest in the first 30 minutes after upload.
If you upload when your audience is most active, those first 30 minutes get maximum views,
which triggers the algorithm to push the video to more people.
""")

st.caption(f"Data source: {source} · Channel: {channel} · Refreshes every 5 min · {now_utc.strftime('%Y-%m-%d %H:%M')} UTC")
