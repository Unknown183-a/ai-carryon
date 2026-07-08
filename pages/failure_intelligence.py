"""
pages/failure_intelligence.py — Phase 5: Failure Intelligence (v1, raw view).

Shows real performance data now that actual_views_24h is populated.
No pattern detection yet — just visibility into what we have, so we
can validate whether AB-predicted scores actually correlate with
real views before building anything that infers rules from it.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from agents.database import db

st.set_page_config(page_title="Failure Intelligence", page_icon="🔍", layout="wide")
st.title("🔍 Failure Intelligence — Phase 5 (v1)")
st.caption("Real 24h performance data, closed via the AB-title loop. No pattern detection yet — raw visibility first.")


@st.cache_data(ttl=300)
def load_data():
    tests = db.get_ab_tests(limit=500)
    df = pd.DataFrame(tests)
    if df.empty:
        return df
    df = df[df["actual_views_24h"].notna()].copy()
    return df


df = load_data()

if df.empty:
    st.warning("No videos with actual_views_24h yet. Run `close_ab_loop.py` after videos cross the 24h mark.")
    st.stop()

st.metric("Videos with real 24h data", len(df))

col1, col2 = st.columns(2)
with col1:
    st.metric("Median 24h views", int(df["actual_views_24h"].median()))
with col2:
    st.metric("Best performer", int(df["actual_views_24h"].max()))

st.subheader("Predicted AB score vs actual 24h views")
st.caption("If these don't correlate, the AB title scorer isn't predicting real performance yet — worth knowing before building anything on top of it.")

fig = px.scatter(
    df,
    x="winner_score",
    y="actual_views_24h",
    color="winner_pattern",
    hover_data=["winner_title", "topic"],
    labels={
        "winner_score": "AB Predicted Score (0-10)",
        "actual_views_24h": "Actual Views (24h)",
        "winner_pattern": "Title Pattern",
    },
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("All videos with real data")
display_df = df[[
    "generated_at", "topic", "winner_title", "winner_pattern",
    "winner_score", "actual_views_24h", "video_id"
]].sort_values("actual_views_24h", ascending=False)
st.dataframe(display_df, use_container_width=True, hide_index=True)

st.subheader("Performance by title pattern")
if df["winner_pattern"].notna().any():
    pattern_stats = df.groupby("winner_pattern")["actual_views_24h"].agg(["mean", "median", "count"]).reset_index()
    pattern_stats.columns = ["Pattern", "Avg Views", "Median Views", "Count"]
    st.dataframe(pattern_stats.sort_values("Avg Views", ascending=False), use_container_width=True, hide_index=True)
else:
    st.info("No pattern data available yet.")
