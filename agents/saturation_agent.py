"""
saturation_agent.py — Phase 1.5: Topic Saturation Engine

Before researching a topic, scores how saturated it is.
Checks how many similar videos were uploaded in the last 24 hours
and how many high-authority channels have already covered it.

Only topics with opportunity_score >= OPPORTUNITY_THRESHOLD should proceed.

Pipeline becomes: Trend -> Saturation Check -> Research

Usage:
    from agents.saturation_agent import check_saturation

    result = check_saturation("OpenAI GPT-5 release")
    if result["proceed"]:
        # hand off to research_agent
    else:
        print(f"Skipping: {result['reason']}")
"""

import os
import time
import logging
from datetime import datetime, timezone, timedelta

from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

# Score threshold — topics below this are skipped
OPPORTUNITY_THRESHOLD = 40

# How many videos uploaded in last 24h is "too saturated"
HIGH_SATURATION_COUNT = 20

# Authority channels in the AI/tech niche — already covering a topic here = penalty
AUTHORITY_CHANNELS = {
    "UCXuqSBlHAE6Xw-yeJA0Tunw": "Linus Tech Tips",
    "UCBcRF18a7Qf58cCRy5xuWwQ": "MrBeast Tech",
    "UC9-y-6csu5WGm29I7JiwpnA": "Computerphile",
    "UCNL8QmkMRMhW6gqLWVFJqEQ": "Two Minute Papers",
    "UCbmNph6atAoGfqLoCL_duAg": "Fireship",
    "UCVHFbw7woebKtYXKApIMFnw": "AI Explained",
    "UCJXGnmhyXPoTAMmWOLVJFTA": "Jeff Su",
}

# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────

def check_saturation(topic: str) -> dict:
    """
    Score a topic for saturation and return a decision.

    Returns:
    {
        "topic": "OpenAI GPT-5 release",
        "proceed": True,
        "opportunity_score": 72,
        "recent_video_count": 8,
        "authority_coverage": ["Fireship", "AI Explained"],
        "reason": "Good opportunity — moderate competition, no dominant authority coverage.",
        "checked_at": "2026-06-20T10:00:00Z"
    }
    """
    if not YOUTUBE_API_KEY:
        logger.warning("YOUTUBE_API_KEY not set — skipping saturation check, proceeding.")
        return _bypass(topic, "No API key — saturation check skipped.")

    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

        recent_count = _count_recent_videos(youtube, topic)
        authority_hits = _check_authority_channels(youtube, topic)

        opportunity_score = _compute_score(recent_count, authority_hits)
        proceed = opportunity_score >= OPPORTUNITY_THRESHOLD

        reason = _build_reason(opportunity_score, recent_count, authority_hits, proceed)

        return {
            "topic": topic,
            "proceed": proceed,
            "opportunity_score": opportunity_score,
            "recent_video_count": recent_count,
            "authority_coverage": authority_hits,
            "reason": reason,
            "checked_at": _now_iso(),
        }

    except Exception as e:
        logger.error(f"Saturation check failed for '{topic}': {e}")
        # Fail open — don't block the pipeline on API errors
        return _bypass(topic, f"Saturation check error: {e}")


# ─────────────────────────────────────────────
# YouTube API helpers
# ─────────────────────────────────────────────

def _count_recent_videos(youtube, topic: str) -> int:
    """Count videos matching the topic uploaded in the last 24 hours."""
    published_after = (
        datetime.now(timezone.utc) - timedelta(hours=24)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        response = youtube.search().list(
            q=topic,
            part="id",
            type="video",
            publishedAfter=published_after,
            maxResults=50,
            relevanceLanguage="en",
            videoDuration="short",  # focus on Shorts competition
        ).execute()

        return response.get("pageInfo", {}).get("totalResults", 0)

    except Exception as e:
        logger.warning(f"Could not count recent videos: {e}")
        return 0


def _check_authority_channels(youtube, topic: str) -> list:
    """
    Check which authority channels have uploaded about this topic
    in the last 7 days. Returns list of channel names that match.
    """
    hits = []
    published_after = (
        datetime.now(timezone.utc) - timedelta(days=7)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    for channel_id, channel_name in AUTHORITY_CHANNELS.items():
        try:
            response = youtube.search().list(
                q=topic,
                part="id",
                type="video",
                channelId=channel_id,
                publishedAfter=published_after,
                maxResults=3,
            ).execute()

            if response.get("items"):
                hits.append(channel_name)

            time.sleep(0.1)  # be gentle with quota

        except Exception as e:
            logger.warning(f"Authority check failed for {channel_name}: {e}")
            continue

    return hits


# ─────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────

def _compute_score(recent_count: int, authority_hits: list) -> int:
    """
    Opportunity score 0–100. Higher = better opportunity.

    Penalties:
    - Recent video count drives down score (more competition = lower score)
    - Each authority channel that covered it subtracts points
    """
    # Base score
    score = 100

    # Volume penalty: scale from 0 (no competition) to -50 (heavily saturated)
    if recent_count >= HIGH_SATURATION_COUNT:
        volume_penalty = 50
    else:
        volume_penalty = int((recent_count / HIGH_SATURATION_COUNT) * 50)

    score -= volume_penalty

    # Authority penalty: -10 per authority channel, max -40
    authority_penalty = min(len(authority_hits) * 10, 40)
    score -= authority_penalty

    return max(score, 0)


def _build_reason(score: int, recent_count: int, authority_hits: list, proceed: bool) -> str:
    parts = []

    if recent_count == 0:
        parts.append("No competing videos in the last 24h.")
    elif recent_count < 5:
        parts.append(f"Low competition ({recent_count} videos in 24h).")
    elif recent_count < HIGH_SATURATION_COUNT:
        parts.append(f"Moderate competition ({recent_count} videos in 24h).")
    else:
        parts.append(f"High saturation ({recent_count} videos in 24h).")

    if authority_hits:
        parts.append(f"Authority channels already covered it: {', '.join(authority_hits)}.")
    else:
        parts.append("No authority channel coverage this week.")

    verdict = (
        f"Opportunity score: {score}/100 — "
        + ("proceeding." if proceed else f"skipping (threshold: {OPPORTUNITY_THRESHOLD}).")
    )
    parts.append(verdict)

    return " ".join(parts)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _bypass(topic: str, reason: str) -> dict:
    return {
        "topic": topic,
        "proceed": True,
        "opportunity_score": -1,
        "recent_video_count": -1,
        "authority_coverage": [],
        "reason": reason,
        "checked_at": _now_iso(),
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────────────────────────
# CLI test: python agents/saturation_agent.py "your topic"
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json

    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "OpenAI GPT-5"
    print(f"Checking saturation for: {topic}\n")
    result = check_saturation(topic)
    print(json.dumps(result, indent=2))
