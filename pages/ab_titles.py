"""
pages/ab_titles.py — Phase 3 Dashboard: A/B Title Performance
Reads from Firestore — works for both English and Hindi channels.
"""

import sys
import os
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

st.set_page_config(page_title="A/B Titles · AI CarryON", page_icon="🎯", layout="wide")

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

st.title("🎯 A/B Title Tester")
st.caption("Which title patterns get the most clicks? Track and learn — per channel.")

# ── Channel selector ────────────────────────────────────────────────────────

channel = st.radio("Channel", ["AI CarryON (English)", "Hindi AI CarryON"], horizontal=True)
is_hindi = channel == "Hindi AI CarryON"

# ── Load from Firestore, fallback to JSON ────────────────────────────────────

@st.cache_data(ttl=120)
def load_logs(hindi: bool):
    try:
        from agents.database import db
        all_tests = db.get_ab_tests(limit=500)
        if hindi:
            filtered = [t for t in all_tests if t.get("topic", "").startswith("[HI]")]
            for t in filtered:
                t["topic"] = t["topic"].replace("[HI] ", "")
        else:
            filtered = [t for t in all_tests if not t.get("topic", "").startswith("[HI]")]

        logs = []
        for t in filtered:
            logs.append({
                "topic": t.get("topic", ""),
                "winner": {
                    "title": t.get("winner_title", ""),
                    "pattern": t.get("winner_pattern", ""),
                    "score": t.get("winner_score", 0),
                },
                "variations": t.get("all_variations", []),
                "generated_at": t.get("generated_at", ""),
            })
        return logs
    except Exception as e:
        print(f"DB load error, falling back to JSON: {e}")

    if hindi:
        return []
    import json
    log_file = os.path.join(os.path.dirname(__file__), "..", "output", "title_ab_log.json")
    if not os.path.exists(log_file):
        return []
    try:
        with open(log_file, "r") as f:
            return json.load(f)
    except Exception:
        return []

logs = load_logs(is_hindi)

if not logs:
    st.info(f"No A/B title data yet for {channel}. Generate some videos first — titles will be logged automatically.")
    st.stop()

# ── Metrics ────────────────────────────────────────────────────────────────

total_tests = len(logs)
all_variations = [v for entry in logs for v in entry.get("variations", [])]
all_winners = [entry["winner"] for entry in logs if "winner" in entry]

avg_winner_score = sum(w["score"] for w in all_winners) / len(all_winners) if all_winners else 0

pattern_wins = {}
pattern_scores = {}
for entry in logs:
    winner = entry.get("winner", {})
    pattern = winner.get("pattern", "unknown")
    score = winner.get("score", 0)
    pattern_wins[pattern] = pattern_wins.get(pattern, 0) + 1
    pattern_scores.setdefault(pattern, []).append(score)

best_pattern = max(pattern_wins, key=pattern_wins.get) if pattern_wins else "—"

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total A/B tests", total_tests)
col2.metric("Avg winner score", f"{avg_winner_score:.1f}/10")
col3.metric("Best pattern", best_pattern)
col4.metric("Titles generated", len(all_variations))

st.divider()

# ── Pattern win chart ──────────────────────────────────────────────────────

st.subheader(f"🏆 Pattern win rate — {channel}")

patterns = list(pattern_wins.keys())
wins = [pattern_wins[p] for p in patterns]
avg_scores = [sum(pattern_scores[p]) / len(pattern_scores[p]) for p in patterns]

fig = go.Figure()
fig.add_trace(go.Bar(
    x=patterns,
    y=wins,
    name="Wins",
    marker_color="#6366f1",
    hovertemplate="<b>%{x}</b><br>Wins: %{y}<extra></extra>",
))
fig.add_trace(go.Scatter(
    x=patterns,
    y=avg_scores,
    name="Avg score",
    yaxis="y2",
    mode="markers+lines",
    marker=dict(size=10, color="#f59e0b"),
    line=dict(color="#f59e0b", width=2),
))
fig.update_layout(
    plot_bgcolor="#0f172a",
    paper_bgcolor="#0f172a",
    font_color="#e2e8f0",
    margin=dict(t=20, b=40, l=50, r=50),
    height=350,
    yaxis=dict(title="Win count"),
    yaxis2=dict(title="Avg score", overlaying="y", side="right", range=[0, 10]),
    legend=dict(orientation="h", y=1.1),
    showlegend=True,
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Recent title tests ────────────────────────────────────────────────────

st.subheader("📋 Recent title tests")

recent = list(reversed(logs[-20:]))
rows = []
for entry in recent:
    winner = entry.get("winner", {})
    rows.append({
        "Topic": entry.get("topic", "")[:40],
        "Winner title": winner.get("title", "")[:55],
        "Pattern": winner.get("pattern", ""),
        "Score": winner.get("score", 0),
        "Generated": entry.get("generated_at", "")[:10],
    })

df = pd.DataFrame(rows)
df.index = range(1, len(df) + 1)
st.dataframe(df, use_container_width=True)

st.divider()

# ── Manual title tester ───────────────────────────────────────────────────

st.subheader(f"🧪 Test a title now — {channel}")

test_topic = st.text_input("Topic", placeholder="e.g. iPhone 17 Pro camera upgrade" if not is_hindi else "e.g. iPhone 17 ka naya feature")
test_script = st.text_area("Script (optional)", placeholder="Paste script here for better results...", height=100)

if st.button("🎯 Generate Title Variations", type="primary"):
    if not test_topic.strip():
        st.warning("Enter a topic first.")
    else:
        with st.spinner("Generating and scoring title variations..."):
            try:
                if is_hindi:
                    from agents_hindi.ab_title_agent import get_best_title_hindi
                    result = get_best_title_hindi(test_topic.strip(), test_script.strip() or test_topic)
                else:
                    from agents.ab_title_agent import get_best_title
                    result = get_best_title(test_topic.strip(), test_script.strip() or test_topic)

                st.success(f"🏆 Winner: **{result['winner']['title']}** (score: {result['winner']['score']}/10, pattern: {result['winner']['pattern']})")

                st.subheader("All variations")
                for i, v in enumerate(result["variations"]):
                    medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
                    st.markdown(f"{medal} **[{v['score']}/10] [{v['pattern']}]** {v['title']}")

                load_logs.clear()

            except Exception as e:
                st.error(f"Error: {e}")

st.caption(f"Channel: {channel} · {total_tests} tests logged · Source: Firestore")
