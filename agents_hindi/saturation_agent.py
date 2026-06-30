"""
agents_hindi/saturation_agent.py — Phase 1.5 for Hindi Channel

Checks how saturated a Hindi topic is before researching.
Same logic as English but searches Hindi-relevant content and
uses Indian authority channels.
"""

import os
import time
import logging
from datetime import datetime, timezone, timedelta

from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

OPPORTUNITY_THRESHOLD = 40
HIGH_SATURATION_COUNT = 20

# Indian tech/AI authority channels
AUTHORITY_CHANNELS_HINDI = {
    "UCqW8jxh4tH1Z1sWPbkGWL4g": "Technical Guruji",
    "UCOhHO2ICt0ti9KAh-QHvttQ": "Trakin Tech",
    "UCXuqSBlHAE6Xw-yeJA0Tunw": "Tech Burner",
    "UCS8a0HnrSyDb0vO-z7QYbXg": "Beebom",
}


def check_saturation_hindi(topic: str) -> dict:
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
        logger.error(f"Hindi saturation check failed for '{topic}': {e}")
        return _bypass(topic, f"Saturation check error: {e}")


def _count_recent_videos(youtube, topic: str) -> int:
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
            relevanceLanguage="hi",
            regionCode="IN",
            videoDuration="short",
        ).execute()

        return response.get("pageInfo", {}).get("totalResults", 0)

    except Exception as e:
        logger.warning(f"Could not count recent Hindi videos: {e}")
        return 0


def _check_authority_channels(youtube, topic: str) -> list:
    hits = []
    published_after = (
        datetime.now(timezone.utc) - timedelta(days=7)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    for channel_id, channel_name in AUTHORITY_CHANNELS_HINDI.items():
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

            time.sleep(0.1)

        except Exception as e:
            logger.warning(f"Authority check failed for {channel_name}: {e}")
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
        parts.append("No competing Hindi videos in the last 24h.")
    elif recent_count < 5:
        parts.append(f"Low competition ({recent_count} videos in 24h).")
    elif recent_count < HIGH_SATURATION_COUNT:
        parts.append(f"Moderate competition ({recent_count} videos in 24h).")
    else:
        parts.append(f"High saturation ({recent_count} videos in 24h).")

    if authority_hits:
        parts.append(f"Indian authority channels already covered it: {', '.join(authority_hits)}.")
    else:
        parts.append("No authority channel coverage this week.")

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
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "iPhone 17 ka naya feature"
    print(f"Checking Hindi saturation for: {topic}\n")
    result = check_saturation_hindi(topic)
    print(json.dumps(result, indent=2))
