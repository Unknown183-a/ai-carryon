# agents_cricket/saturation_agent.py
"""
agents_cricket/saturation_agent.py — Phase 1.5 for the Cricket Channel

Same intent as agents/saturation_agent.py and agents_hindi/saturation_agent.py:
score how saturated a topic already is before spending a CricAPI + LLM call
researching it. For cricket the "topic" is a specific match, so this checks
how many recent Shorts the major Indian cricket authority channels have
already posted about the same two teams — a proxy for "this exact match
moment is probably already everywhere."

Cricket differs from a generic tech topic in one important way: dedup
against agents_cricket.database.get_all_posted_match_ids() already stops
the SAME match_id from being posted twice, so this agent is not a hard
gate — it fails open by design and is meant to nudge match SELECTION
(prefer less-covered matches when several are available), not block
the pipeline outright the way it would for a discretionary tech topic.
"""

import os
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

OPPORTUNITY_THRESHOLD = 35
HIGH_SATURATION_COUNT = 15

# Major Indian cricket authority channels — heavy same-day coverage from
# these on the same two teams is a strong saturation signal.
AUTHORITY_CHANNELS_CRICKET = {
    "UCiWLfSweyRNmLpgEHekhoAg": "ICC",
    "UCzT2sVjbLTKQTCV5rZTT3sw": "Star Sports Cricket",
    "UCcSJDNaN3IvvR5VJq7hAHrw": "Cricbuzz",
    "UCS-KzcxlSU8pyoZoKzDG-4Q": "ESPNcricinfo",
}


def check_saturation_cricket(match_label: str, teams=None) -> dict:
    """match_label: short text used for the YouTube search query, e.g.
    'India vs Australia'. teams: optional list, used only for logging."""
    if not YOUTUBE_API_KEY:
        logger.warning("YOUTUBE_API_KEY not set — skipping cricket saturation check")
        return _bypass(match_label, "No API key — saturation check skipped.")

    try:
        from googleapiclient.discovery import build
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

        recent_count = _count_recent_videos(youtube, match_label)
        authority_hits = _check_authority_channels(youtube, match_label)

        opportunity_score = _compute_score(recent_count, authority_hits)
        proceed = opportunity_score >= OPPORTUNITY_THRESHOLD

        reason = _build_reason(opportunity_score, recent_count, authority_hits, proceed)

        return {
            "match_label": match_label,
            "teams": teams or [],
            "proceed": proceed,
            "opportunity_score": opportunity_score,
            "recent_video_count": recent_count,
            "authority_coverage": authority_hits,
            "reason": reason,
            "checked_at": _now_iso(),
        }

    except Exception as e:
        logger.error(f"Cricket saturation check failed for '{match_label}': {e}")
        return _bypass(match_label, f"Saturation check error: {e}")


def rank_topics_by_opportunity(topics, limit=None):
    """Given the list from trending_agent.get_all_topics(), returns the
    same list re-ordered so less-saturated matches come first. News and
    upcoming-match items (no scorecard yet) always sort ahead of finished
    matches, since there's nothing to check saturation against yet and
    they're time-sensitive."""
    scored = []
    for t in topics:
        if t.get("topic_type") in ("news", "upcoming", "live"):
            scored.append((100, t))  # always prioritized — no saturation check needed
            continue
        teams = t.get("teams", [])
        label = " vs ".join(teams) if teams else t.get("name", t.get("title", ""))
        result = check_saturation_cricket(label, teams=teams)
        scored.append((result["opportunity_score"], t))

    scored.sort(key=lambda x: x[0], reverse=True)
    ranked = [t for _, t in scored]
    return ranked[:limit] if limit else ranked


def _count_recent_videos(youtube, match_label, days=2):
    published_after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        resp = youtube.search().list(
            q=match_label,
            part="id",
            type="video",
            order="date",
            publishedAfter=published_after,
            maxResults=50,
            regionCode="IN",
        ).execute()
        return len(resp.get("items", []))
    except Exception as e:
        logger.warning(f"Cricket recent-video count failed: {e}")
        return 0


def _check_authority_channels(youtube, match_label, days=2):
    published_after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hits = {}
    for channel_id, channel_name in AUTHORITY_CHANNELS_CRICKET.items():
        try:
            resp = youtube.search().list(
                q=match_label,
                part="id",
                type="video",
                channelId=channel_id,
                publishedAfter=published_after,
                maxResults=5,
            ).execute()
            count = len(resp.get("items", []))
            if count > 0:
                hits[channel_name] = count
        except Exception as e:
            logger.warning(f"Authority check failed for {channel_name}: {e}")
    return hits


def _compute_score(recent_count, authority_hits):
    score = 100
    score -= min(recent_count * 3, 60)
    score -= min(len(authority_hits) * 10, 30)
    return max(score, 0)


def _build_reason(score, recent_count, authority_hits, proceed):
    if proceed:
        return f"Opportunity score {score}/100 — {recent_count} recent videos, {len(authority_hits)} authority channels covering it. Good to proceed."
    return (
        f"Opportunity score {score}/100 (below {OPPORTUNITY_THRESHOLD}) — {recent_count} recent videos, "
        f"covered by {', '.join(authority_hits.keys()) or 'no'} authority channels. Consider a less-covered match."
    )


def _bypass(match_label, reason):
    return {
        "match_label": match_label,
        "teams": [],
        "proceed": True,
        "opportunity_score": 100,
        "recent_video_count": 0,
        "authority_coverage": {},
        "reason": reason,
        "checked_at": _now_iso(),
    }


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    import sys, json
    label = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "India vs Australia"
    print(json.dumps(check_saturation_cricket(label), indent=2, default=str))
