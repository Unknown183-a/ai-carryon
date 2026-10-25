"""
semantic_report.py — pure helpers behind the dashboard's "Semantic Brain" page (pages/semantic_brain.py).
No Streamlit, no database, no clock: everything takes plain dicts/lists so it can be unit-tested.

Reports are the dicts tools/eval_semantic.py produces (stored in semantic_eval_reports); decision rows are the dicts
Database.get_topic_decisions returns (one row per candidate per ranking).
"""
import math

CHANNELS = [("english", "English"), ("hindi", "Hindi"), ("cricket", "Cricket"), ("finance", "Finance"),
            ("gaming", "Gaming"), ("horror", "Horror"), ("bhakti", "Bhakti")]
CHANNEL_NAMES = dict(CHANNELS)

PASSED, NOT_YET, NO_DATA = "passed", "not_yet", "no_data"
_ICON = {PASSED: "✅", NOT_YET: "⏳", NO_DATA: "—"}
_LABEL = {PASSED: "Ready to consider", NOT_YET: "Not yet", NO_DATA: "No data yet"}


def _num(v):
    """float or None; NaN/inf/garbage become None (JSON round-trips NaN, and a missing value must not crash a page)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _assess(report):
    """(state, code, data): what the gate decided and why, as data. gate_status and summary_row both phrase it."""
    if not report:
        return NO_DATA, "never", {}
    n = int(report.get("videos_with_neighbours") or 0)
    need = int(report.get("min_eval") or 30)
    if n == 0:
        return NO_DATA, "no_evidence", {}
    if n < need:
        return NOT_YET, "few", {"n": n, "need": need}
    ci = report.get("gain_ci95") or [None, None]
    lo = _num(ci[0]) if len(ci) > 0 else None
    rho = _num(report.get("spearman"))
    if lo is None or lo <= 0:
        return NOT_YET, "interval", {"lo": lo}
    if rho is None or rho <= 0:
        return NOT_YET, "rank", {"rho": rho}
    if not report.get("gate_passed"):
        return NOT_YET, "flag", {}
    return PASSED, "ok", {}


def _signed(v):
    return "unknown" if v is None else f"{v:+.2f}"


_LONG = {
    "never": lambda d: "This channel has not been evaluated yet.",
    "no_evidence": lambda d: "No video had similar past videos at the time it was published.",
    "few": lambda d: f"Only {d['n']} of the {d['need']} scored videos needed so far.",
    "interval": lambda d: ("The improvement over predicting the channel median could still be luck "
                           f"(lower bound {_signed(d['lo'])}, it must be above 0)."),
    "rank": lambda d: f"Higher scores did not go with more views (rank correlation {_signed(d['rho'])}, it must be positive).",
    "flag": lambda d: "The evaluation did not mark this channel as passed.",
    "ok": lambda d: "Beats the channel median with enough data. Promotion from shadow is now a judgement call.",
}
_SHORT = {
    "never": lambda d: "Not evaluated yet",
    "no_evidence": lambda d: "No similar past videos yet",
    "few": lambda d: f"Needs {d['need']}, has {d['n']}",
    "interval": lambda d: f"Gain could be luck (low end {_signed(d['lo'])})",
    "rank": lambda d: f"Higher scores, not more views ({_signed(d['rho'])})",
    "flag": lambda d: "Not marked as passed",
    "ok": lambda d: "All checks met",
}


def gate_status(report):
    """(state, label, reason) for one evaluation report. The reason says, in plain words, what is still missing.
    Mirrors the gate in tools/eval_semantic.py: enough scored videos AND an improvement interval above zero AND a
    positive rank correlation. The numbers decide; the stored gate_passed flag alone is never trusted."""
    state, code, data = _assess(report)
    return state, _tag(state), _LONG[code](data)


def _tag(state):
    return f"{_ICON[state]} {_LABEL[state]}"


def latest_per_channel(reports):
    """{channel: newest report}. `reports` may be in any order; evaluated_at (ISO) decides."""
    out = {}
    for r in reports:
        ch = r.get("channel")
        if ch and (ch not in out or str(r.get("evaluated_at", "")) > str(out[ch].get("evaluated_at", ""))):
            out[ch] = r
    return out


def history(reports, channel):
    """Oldest-first list of {evaluated_at, scored, mean_gain, lo, hi, spearman} for one channel's chart."""
    rows = []
    for r in sorted((r for r in reports if r.get("channel") == channel), key=lambda r: str(r.get("evaluated_at", ""))):
        ci = r.get("gain_ci95") or [None, None]
        rows.append({"evaluated_at": r.get("evaluated_at"), "scored": int(r.get("videos_with_neighbours") or 0),
                     "mean_gain": _num(r.get("mean_gain")), "lo": _num(ci[0]) if ci else None,
                     "hi": _num(ci[1]) if len(ci) > 1 else None, "spearman": _num(r.get("spearman"))})
    return rows


def summary_row(channel, report):
    """One display row for the overview table."""
    state, code, data = _assess(report)
    label, reason = _tag(state), _SHORT[code](data)
    report = report or {}
    ci = report.get("gain_ci95") or [None, None]
    lo, hi = (_num(ci[0]), _num(ci[1])) if len(ci) > 1 else (None, None)
    return {"channel": CHANNEL_NAMES.get(channel, channel), "status": label, "why": reason,
            "scored": int(report.get("videos_with_neighbours") or 0),
            "mean_gain": _num(report.get("mean_gain")),
            "interval": None if lo is None or hi is None else f"{lo:+.2f} to {hi:+.2f}",
            "spearman": _num(report.get("spearman")),
            "evaluated_at": report.get("evaluated_at")}


def _shadow_top(brain_scores_by_topic):
    """{brain_id: top topic} for each shadow Brain that expressed a preference (all-equal scores = abstained)."""
    per_brain = {}
    for topic, scores in brain_scores_by_topic.items():
        for brain_id, info in (scores or {}).items():
            if info.get("role") == "shadow" and info.get("score") is not None:
                per_brain.setdefault(brain_id, {})[topic] = float(info["score"])
    tops = {}
    for brain_id, by_topic in per_brain.items():
        if len(set(by_topic.values())) < 2:
            continue
        tops[brain_id] = max(by_topic, key=lambda t: (by_topic[t], t))
    return tops


def decision_summary(rows):
    """Counts from the decision log for the dashboard: rankings logged, how many ended in a selection, how many
    included a shadow Brain with an opinion, and how often that shadow Brain's top pick was the topic actually used."""
    runs = {}
    for r in rows:
        run = runs.setdefault(r["run_id"], {"decided_at": r.get("decided_at"), "channel": r.get("channel"),
                                            "selected": None, "scores": {}, "source": r.get("source")})
        run["scores"][r["topic"]] = r.get("brain_scores") or {}
        if r.get("selected"):
            run["selected"] = r["topic"]
    with_selection = [r for r in runs.values() if r["selected"]]
    with_shadow = [r for r in runs.values() if _shadow_top(r["scores"])]
    comparable = [r for r in with_selection if _shadow_top(r["scores"])]
    agree = sum(1 for r in comparable if r["selected"] in _shadow_top(r["scores"]).values())
    return {"rankings": len(runs), "candidates": len(rows), "with_selection": len(with_selection),
            "with_shadow_opinion": len(with_shadow), "comparable": len(comparable), "shadow_agreed": agree,
            "latest": max((r["decided_at"] for r in runs.values() if r["decided_at"]), default=None)}
