"""
pages/schedule.py — Phase 4 Dashboard: Adaptive Scheduling
Shows optimal upload windows and current schedule recommendation.
"""

import sys
import os
from datetime import datetime, timezone

import streamlit as st
import plotly.graph_objects as go

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

st.set_page_config(page_title="Schedule · AI CarryON", page_icon="🕐", layout="wide")

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

# ── Load data ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_recommendation():
    try:
        from agents.adaptive_scheduler import get_schedule_recommendation, get_best_upload_windows
        rec = get_schedule_recommendation()
        windows, source = get_best_upload_windows(top_n=24)
        return rec, windows, source
    except Exception as e:
        return {"status": "error", "message": str(e)}, [], "error"

with st.spinner("Analyzing view velocity data..."):
    rec, windows, source = load_recommendation()

# ── Status banner ─────────────────────────────────────────────────────────

if rec["status"] == "insufficient_data":
    st.warning(f"⏳ {rec['message']}")
elif rec["status"] == "ready":
    st.success(f"✅ {rec['message']}")
elif rec["status"] == "error":
    st.error(f"Error: {rec['message']}")

# ── Top metrics ────────────────────────────────────────────────────────────

best_hour = rec.get("best_hour")
top_windows = rec.get("windows", [])

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

st.subheader("📈 View velocity by hour (UTC)")

try:
    from agents.adaptive_scheduler import get_peak_hours_analysis
    peak_hours, _ = get_peak_hours_analysis()

    hours = list(range(24))
    velocities = [peak_hours.get(h, {}).get("avg_velocity", 0) for h in hours]
    samples = [peak_hours.get(h, {}).get("sample_count", 0) for h in hours]
    labels = [f"{h:02d}:00" for h in hours]
    top_set = {w["hour"] for w in top_windows[:3]}
    colors = ["#6366f1" if h in top_set else "#334155" for h in hours]

    fig = go.Figure(go.Bar(
        x=labels,
        y=velocities,
        marker_color=colors,
        hovertemplate="<b>%{x} UTC</b><br>Avg velocity: %{y:.1f} views/hr<br>Samples: %{customdata}<extra></extra>",
        customdata=samples,
    ))

    # Mark current hour
    fig.add_vline(
        x=now_utc.strftime("%H:00"),
        line_dash="dash",
        line_color="#f59e0b",
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
    import pandas as pd
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
    df.index = ["🥇","🥈","🥉"] + [f"{i+4}th" for i in range(len(df)-3)]
    df.index = df.index[:len(df)]
    st.dataframe(df, use_container_width=True)

st.divider()

# ── How it works ──────────────────────────────────────────────────────────

with st.expander("How adaptive scheduling works"):
    st.markdown("""
**Phase 4 logic:**

1. Every hour, the view tracker records how many views each video gained
2. It calculates *velocity* = views gained ÷ hours elapsed for each snapshot pair
3. It groups velocities by the UTC hour they were recorded
4. The hour with the highest average velocity = best upload time

**Scheduler behavior:**
- If best hour is within 90 minutes → waits and uploads at that hour
- If best hour is more than 90 minutes away → uploads immediately (doesn't waste time)
- If not enough data yet → uploads immediately

**Why this matters:**
YouTube's algorithm boosts videos hardest in the first 30 minutes after upload.
If you upload when your audience is most active, those first 30 minutes get maximum views,
which triggers the algorithm to push the video to more people.
""")

st.caption(f"Data source: {source} · Refreshes every 5 min · {now_utc.strftime('%Y-%m-%d %H:%M')} UTC")
