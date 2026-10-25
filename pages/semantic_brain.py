"""
pages/semantic_brain.py — Semantic Brain: does "how did similar past videos do?" actually predict views?

Shows, per channel, the latest weekly evaluation (tools/eval_semantic.py --save), whether the channel has earned
promotion out of shadow mode and, if not, exactly what is still missing; how the evaluation has moved over time;
and a live summary of the Brain decision log (what was offered, what the shadow Brain thought, what was used).
Read-only: nothing here changes how the Brain behaves.
"""
import inspect
import os
import sys

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

st.set_page_config(page_title="Semantic Brain · AI CarryON", page_icon="🧠", layout="wide")

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

from agents import semantic_report as sr  # noqa: E402
from agents.database import db  # noqa: E402

TZ = "Asia/Kolkata"
MIN_EVAL_DEFAULT = 30


def alt_text(fn, text):
    """`alt=` (accessible description) only exists on newer Streamlit versions; pass it when supported."""
    return {"alt": text} if "alt" in inspect.signature(fn).parameters else {}


def ist(value, fmt="%d %b %Y, %H:%M"):
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    return "—" if pd.isna(ts) else ts.tz_convert(TZ).strftime(fmt) + " IST"


@st.cache_data(ttl=300, show_spinner=False)
def load_reports():
    return db.get_semantic_eval_reports(limit=1000)


@st.cache_data(ttl=300, show_spinner=False)
def load_decisions():
    return db.get_topic_decisions(limit=5000)


st.title("🧠 Semantic Brain")
st.caption("Does \"how did the most similar past videos do?\" predict real views? Read-only; it changes nothing the pipeline does.")

with st.container(border=True):
    st.markdown(
        "**How to read this page.** The semantic Brain runs in *shadow*: it scores every candidate topic and the "
        "scores are logged, but it never decides which topic is used. Each week the evaluation replays your video "
        "history exactly as it looked at each publish time and checks whether the Brain's guess beat the simple "
        "guess \"this video will get about the channel's median views\". A channel only becomes **Ready to "
        "consider** with enough scored videos, an improvement that is clearly above zero, and higher scores going "
        "with more views. Until then, keep it in shadow."
    )

top_left, _ = st.columns([1, 6])
with top_left:
    if st.button("Refresh data", icon=":material/refresh:"):
        st.cache_data.clear()
        st.rerun()

try:
    reports = load_reports()
    decisions = load_decisions()
except Exception as e:  # never show a stack trace or connection details on a dashboard
    st.error(f"Could not read the database ({type(e).__name__}).")
    st.stop()

latest = sr.latest_per_channel(reports)

# ── Overview ────────────────────────────────────────────────────────────────

st.subheader("Evaluation by channel")
if not reports:
    st.info(
        "No evaluation has been saved yet. It runs weekly (Mondays, 09:00 IST) once the repository variables "
        "`BRAIN_TEXT_MODEL_NAME` and `BRAIN_TEXT_MODEL_REVISION` are set. To run it now: GitHub → Actions → "
        "Semantic Brain evaluation → Run workflow."
    )
rows = [sr.summary_row(ch, latest.get(ch)) for ch, _ in sr.CHANNELS]


def fmt(value, pattern):
    return "—" if value is None else pattern % value


table = pd.DataFrame([{
    "Channel": r["channel"],
    "Status": r["status"],
    "Scored videos": r["scored"],
    "Gain vs median": fmt(r["mean_gain"], "%+.2f"),
    "95% interval": r["interval"] or "—",
    "Rank correlation": fmt(r["spearman"], "%+.2f"),
    "Last evaluated": ist(r["evaluated_at"]) if r["evaluated_at"] else "—",
    "What is missing": r["why"],
} for r in rows])
st.dataframe(
    table,
    hide_index=True,
    width="stretch",
    column_config={
        "Scored videos": st.column_config.NumberColumn(help=f"Needs at least {MIN_EVAL_DEFAULT}."),
        "Gain vs median": st.column_config.TextColumn(
            help="Average improvement over guessing the channel median, in log-views error. 0 = no better."),
        "95% interval": st.column_config.TextColumn(help="Must stay above 0 to count."),
        "Rank correlation": st.column_config.TextColumn(help="Do higher scores go with more views? Must be above 0."),
        "What is missing": st.column_config.TextColumn(width="medium"),
    },
    **alt_text(st.dataframe, "Latest semantic Brain evaluation for each channel, with its status and what is still missing"),
)

# ── Channel detail ──────────────────────────────────────────────────────────

st.subheader("Channel detail")
channel = st.selectbox("Channel", [c for c, _ in sr.CHANNELS], format_func=lambda c: sr.CHANNEL_NAMES[c])
report = latest.get(channel)
state, label, why = sr.gate_status(report)
label = label.split(" ", 1)[1]   # the table shows the icon; the banner colour already says it

if state == sr.PASSED:
    st.success(f"{label}. {why}")
elif state == sr.NOT_YET:
    st.warning(f"{label}. {why}")
else:
    st.info(f"{label}. {why}")

if report:
    need = int(report.get("min_eval") or MIN_EVAL_DEFAULT)
    scored = int(report.get("videos_with_neighbours") or 0)
    ci = report.get("gain_ci95") or [None, None]
    summary = sr.summary_row(channel, report)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Scored videos", f"{scored} / {need}", border=True,
              help="Videos that had similar past videos when they were published. The gate needs the full amount.")
    c2.metric("Gain vs channel median", "—" if summary["mean_gain"] is None else f"{summary['mean_gain']:+.2f}",
              border=True, help="Above 0 means the Brain's guess was closer to real views than the median guess.")
    c3.metric("95% interval", summary["interval"] or "—", border=True,
              help="The plausible range of that gain. Its lower end must be above 0.")
    c4.metric("Rank correlation", "—" if summary["spearman"] is None else f"{summary['spearman']:+.2f}", border=True,
              help="Do higher-scored topics get more views? Must be above 0.")
    st.progress(min(1.0, scored / need),
                text=f"{scored} scored videos (enough: {need} needed)" if scored >= need
                else f"{scored} of {need} scored videos needed")

    mb, ms = report.get("mae_baseline"), report.get("mae_semantic")
    if isinstance(mb, (int, float)) and isinstance(ms, (int, float)):
        st.caption(f"Average error in log-views: guessing the median {mb:.2f}, semantic Brain {ms:.2f} "
                   f"({'lower is better' if ms < mb else 'the Brain is not closer yet'}).")
    model = report.get("model_id") or "unknown model"
    rev = (report.get("revision") or "")[:8]
    st.caption(f"Evaluated {ist(report.get('evaluated_at'))} · model {model}"
               f"{' @ ' + rev if rev else ''} · outcome definition {report.get('outcome', 'unknown')} · "
               f"{int(report.get('videos_with_outcome') or 0)} videos with a known 24h outcome")

hist = sr.history(reports, channel)
st.markdown("**Over time**")
if len(hist) == 0:
    st.caption("No history for this channel yet.")
else:
    df = pd.DataFrame(hist)
    df["when"] = pd.to_datetime(df["evaluated_at"], utc=True, errors="coerce")
    df["Evaluated"] = df["when"].map(lambda v: ist(v))
    base = alt.Chart(df).encode(x=alt.X("when:T", title="Evaluation date", axis=alt.Axis(format="%d %b", labelAngle=0, tickCount=6)))
    band = base.mark_area(opacity=0.18).encode(y=alt.Y("lo:Q", title="Gain vs channel median"), y2="hi:Q")
    line = base.mark_line(point=True).encode(
        y="mean_gain:Q",
        tooltip=[alt.Tooltip("Evaluated:N"), alt.Tooltip("scored:Q", title="Scored videos"),
                 alt.Tooltip("mean_gain:Q", title="Gain", format="+.2f"),
                 alt.Tooltip("spearman:Q", title="Rank correlation", format="+.2f")])
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(strokeDash=[4, 4]).encode(y="y:Q")
    st.altair_chart(band + line + zero, width="stretch",
                    **alt_text(st.altair_chart, "Gain over the channel median for each weekly evaluation, "
                                                "with its 95% interval shaded and a dashed line at zero"))
    st.caption("The shaded band is the 95% interval. The Brain only counts once the whole band is above the dashed zero line.")

# ── Live decision log ───────────────────────────────────────────────────────

st.subheader("Decision log")
mine = [r for r in decisions if r.get("channel") == channel]
dsum = sr.decision_summary(mine)
if dsum["rankings"] == 0:
    st.info("Nothing logged for this channel yet. Rankings appear here after the first run with the Brain enabled.")
else:
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Rankings logged", dsum["rankings"], border=True)
    d2.metric("Candidates logged", dsum["candidates"], border=True,
              help="Every topic that was offered, not only the one that was published.")
    d3.metric("Ended in a pick", dsum["with_selection"], border=True,
              help="Rankings where the pipeline went on to use one of the topics.")
    agreed = "—" if dsum["comparable"] == 0 else f"{dsum['shadow_agreed']} of {dsum['comparable']}"
    d4.metric("Shadow Brain agreed", agreed, border=True,
              help="How often the semantic Brain's top-scored topic was the one actually used. "
                   "Only counts rankings where it had an opinion.")
    st.caption("Agreement is not accuracy: it only shows how often the shadow Brain would have chosen the same topic. "
               "Whether it chooses *better* is what the weekly evaluation measures.")

    runs = {}
    for r in mine:
        run = runs.setdefault(r["run_id"], {"when": r.get("decided_at"), "n": 0, "picked": "—", "source": r.get("source")})
        run["n"] += 1
        if r.get("selected"):
            run["picked"] = r["topic"]
    recent = sorted(runs.values(), key=lambda x: str(x["when"]), reverse=True)[:15]
    log = pd.DataFrame([{"When": ist(x["when"]), "Candidates": x["n"], "Topic used": x["picked"],
                         "Engine result": x["source"] or "—"} for x in recent])
    st.markdown("**Most recent rankings**")
    st.dataframe(log, hide_index=True, width="stretch",
                 **alt_text(st.dataframe, "The 15 most recent Brain rankings for this channel and the topic used"))
