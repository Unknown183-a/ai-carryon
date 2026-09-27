"""
agents_bhakti/saturation_agent.py — Phase 1.5 for the Bhakti Channel

Same scoring logic as the English/Hindi saturation agents, adapted for
devotional content: checks recent competing videos on the same topic and,
optionally, coverage by known large Bhakti/devotional channels (configure
their channel IDs via BHAKTI_AUTHORITY_CHANNEL_IDS — comma separated — since
those IDs vary and aren't hardcoded here).
"""

import os
import time
import logging
from datetime import datetime, timezone, timedelta

from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

OPPORTUNITY_THRESHOLD = 35  # devotional catalogue is evergreen — slightly more permissive than tech
HIGH_SATURATION_COUNT = 25

# Optional: comma-separated YouTube channel IDs of big devotional channels
# (e.g. T-Series Bhakti Sagar, Shemaroo Bhakti) to treat as "authority"
# coverage. Left empty by default since exact IDs should be confirmed
# before use — set via env var when you have them.
_raw_authority = os.environ.get("BHAKTI_AUTHORITY_CHANNEL_IDS", "")
AUTHORITY_CHANNEL_IDS = [c.strip() for c in _raw_authority.split(",") if c.strip()]


def check_saturation_bhakti(topic: str) -> dict:
    if not YOUTUBE_API_KEY:
        logger.warning("YOUTUBE_API_KEY not set — skipping saturation check")
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
        logger.error(f"Bhakti saturation check failed for '{topic}': {e}")
        return _bypass(topic, f"Saturation check error: {e}")


def _count_recent_videos(youtube, topic: str) -> int:
    published_after = (
        datetime.now(timezone.utc) - timedelta(hours=48)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        response = youtube.search().list(
            q=topic,
            part="id",
            type="video",
            publishedAfter=published_after,
            maxResults=50,
            relevanceLanguage="hi",
            regionCode="IN",
            videoDuration="short",
        ).execute()

        return response.get("pageInfo", {}).get("totalResults", 0)

    except Exception as e:
        logger.warning(f"Could not count recent Bhakti videos: {e}")
        return 0


def _check_authority_channels(youtube, topic: str) -> list:
    if not AUTHORITY_CHANNEL_IDS:
        return []

    hits = []
    published_after = (
        datetime.now(timezone.utc) - timedelta(days=14)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    for channel_id in AUTHORITY_CHANNEL_IDS:
        try:
            response = youtube.search().list(
                q=topic,
                part="snippet",
                type="video",
                channelId=channel_id,
                publishedAfter=published_after,
                maxResults=3,
            ).execute()

            items = response.get("items", [])
            if items:
                hits.append(items[0]["snippet"].get("channelTitle", channel_id))

            time.sleep(0.1)

        except Exception as e:
            logger.warning(f"Authority check failed for {channel_id}: {e}")
            continue

    return hits


def _compute_score(recent_count: int, authority_hits: list) -> int:
    score = 100
    if recent_count >= HIGH_SATURATION_COUNT:
        volume_penalty = 50
    else:
        volume_penalty = int((recent_count / HIGH_SATURATION_COUNT) * 50)
    score -= volume_penalty
    authority_penalty = min(len(authority_hits) * 10, 40)
    score -= authority_penalty
    return max(score, 0)


def _build_reason(score: int, recent_count: int, authority_hits: list, proceed: bool) -> str:
    parts = []
    if recent_count == 0:
        parts.append("No competing devotional videos in the last 48h.")
    elif recent_count < 5:
        parts.append(f"Low competition ({recent_count} videos in 48h).")
    elif recent_count < HIGH_SATURATION_COUNT:
        parts.append(f"Moderate competition ({recent_count} videos in 48h).")
    else:
        parts.append(f"High saturation ({recent_count} videos in 48h).")

    if authority_hits:
        parts.append(f"Large Bhakti channels already covered it: {', '.join(authority_hits)}.")
    else:
        parts.append("No configured authority-channel coverage found.")

    verdict = (
        f"Opportunity score: {score}/100 — "
        + ("proceeding." if proceed else f"skipping (threshold: {OPPORTUNITY_THRESHOLD}).")
    )
    parts.append(verdict)
    return " ".join(parts)


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


if __name__ == "__main__":
    import sys, json
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hanuman ji ka Sanjeevani booti laane ka prasang"
    print(f"Checking Bhakti saturation for: {topic}\n")
    result = check_saturation_bhakti(topic)
    print(json.dumps(result, indent=2))
