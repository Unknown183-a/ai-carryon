# agents_cricket/format_router.py
"""Cricket V2 Phase 2 (step 7) — content format router. Rule-based (no LLM
call). Avoids repeating a format used in the last `format_cooldown` videos."""

FORMAT_COOLDOWN = 2

FORMATS = {
    "MATCH_MOMENT": "Pick the single most dramatic moment of the match and tell only that.",
    "PLAYER_STORY": "Tell the standout player's performance as a story: what he did, "
                    "against what odds, and what it changed for the team.",
    "MATCH_TURNING_POINT": "Explain the one passage of play that decided the match: "
                           "before it, the swing, and why the result could not recover.",
    "CRICKET_RECORD": "Build the story around a record, milestone or unusual number in the data.",
    "MATCH_RECAP": "Short result-first recap, but still one clear storyline, not a list of scores.",
    "MATCH_PREVIEW": "Preview the upcoming match: the stakes, the teams, and the one question "
                     "that decides it. Do not predict a score or invent form/head-to-head numbers.",
    "CRICKET_NEWS": "Explain the news item: what happened, why it matters to fans, "
                    "what could follow. Use only what the headline states.",
}

_TURNING = ("collapse", "all out", "chase", "super over", "last ball", "won by 1 ", "won by 2 ", "by 1 run",
            "by 2 runs", "by 1 wicket", "by 2 wickets", "tied")
_RECORD = ("record", "century", "hundred", "hat-trick", "hat trick", "fifer", "highest", "lowest")


def route_format(topic_type, summary, structured, recent_formats=None):
    """Returns a format name from FORMATS."""
    recent = list(recent_formats or [])[-FORMAT_COOLDOWN:]
    if topic_type == "news":
        return "CRICKET_NEWS"
    if topic_type == "upcoming":
        return "MATCH_PREVIEW"

    text = (summary or "").lower()
    cands = []
    if any(k in text for k in _TURNING):
        cands.append("MATCH_TURNING_POINT")
    if any(k in text for k in _RECORD):
        cands.append("CRICKET_RECORD")
    if (structured or {}).get("standout_player"):
        cands.append("PLAYER_STORY")
    cands += ["MATCH_MOMENT", "MATCH_RECAP"]

    seen = []
    for c in cands:
        if c not in seen:
            seen.append(c)
    for c in seen:
        if c not in recent:
            return c
    return seen[0]
