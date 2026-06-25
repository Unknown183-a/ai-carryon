"""
agents/comparison_agent.py — Phase 2: Competitor Comparison Engine (English)

For a given topic, fetches top 10 competing videos from YouTube,
benchmarks them against your channel's video on the same topic,
and returns actionable insights.

Usage:
    from agents.comparison_agent import compare_topic
    result = compare_topic("Claude 4 Opus benchmark")
"""

import os
import time
from datetime import datetime, timezone, timedelta
from agents.analytics_agent import authenticate

YOUR_CHANNEL_ID = os.environ.get("YOUTUBE_CHANNEL_ID", "")

def compare_topic(topic: str) -> dict:
    """
    Compare your video on this topic against top competitors.
    Returns insights dict with benchmarks and recommendations.
    """
    try:
        yt = authenticate()

        competitors = _fetch_competing_videos(yt, topic)
        your_video  = _fetch_your_video(yt, topic)
        insights    = _generate_insights(your_video, competitors, topic)

        return {
            "topic": topic,
            "your_video": your_video,
            "competitors": competitors,
            "insights": insights,
            "checked_at": _now_iso(),
        }

    except Exception as e:
        return {"topic": topic, "error": str(e), "checked_at": _now_iso()}


def _fetch_competing_videos(yt, topic: str) -> list:
    """Fetch top 10 competing videos for the topic uploaded in last 7 days."""
    published_after = (
        datetime.now(timezone.utc) - timedelta(days=7)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    search_resp = yt.search().list(
        q=topic,
        part="id,snippet",
        type="video",
        order="viewCount",
        publishedAfter=published_after,
        maxResults=10,
        relevanceLanguage="en",
    ).execute()

    video_ids = [
        item["id"]["videoId"]
        for item in search_resp.get("items", [])
        if item["id"].get("videoId")
    ]

    if not video_ids:
        return []

    stats_resp = yt.videos().list(
        part="statistics,snippet,contentDetails",
        id=",".join(video_ids),
    ).execute()

    competitors = []
    for item in stats_resp.get("items", []):
        snippet = item["snippet"]
        stats   = item.get("statistics", {})
        dur     = item.get("contentDetails", {}).get("duration", "")

        views    = int(stats.get("viewCount", 0))
        likes    = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))

        published_str = snippet.get("publishedAt", "")
        upload_hour   = _parse_hour(published_str)

        competitors.append({
            "video_id":       item["id"],
            "title":          snippet.get("title", ""),
            "channel":        snippet.get("channelTitle", ""),
            "views":          views,
            "likes":          likes,
            "comments":       comments,
            "engagement_rate": round(likes / views * 100, 2) if views else 0,
            "published":      published_str[:10],
            "upload_hour_utc": upload_hour,
            "duration_seconds": _parse_duration(dur),
            "title_length":   len(snippet.get("title", "")),
            "url":            f"https://youtube.com/watch?v={item['id']}",
        })

    return sorted(competitors, key=lambda x: x["views"], reverse=True)


def _fetch_your_video(yt, topic: str) -> dict:
    """Find your most recent video matching this topic."""
    if not YOUR_CHANNEL_ID:
        return {}

    search_resp = yt.search().list(
        q=topic,
        part="id,snippet",
        type="video",
        channelId=YOUR_CHANNEL_ID,
        order="date",
        maxResults=1,
    ).execute()

    items = search_resp.get("items", [])
    if not items:
        return {}

    video_id = items[0]["id"].get("videoId")
    if not video_id:
        return {}

    stats_resp = yt.videos().list(
        part="statistics,snippet,contentDetails",
        id=video_id,
    ).execute()

    if not stats_resp.get("items"):
        return {}

    item    = stats_resp["items"][0]
    snippet = item["snippet"]
    stats   = item.get("statistics", {})
    dur     = item.get("contentDetails", {}).get("duration", "")

    views    = int(stats.get("viewCount", 0))
    likes    = int(stats.get("likeCount", 0))
    comments = int(stats.get("commentCount", 0))

    return {
        "video_id":        video_id,
        "title":           snippet.get("title", ""),
        "views":           views,
        "likes":           likes,
        "comments":        comments,
        "engagement_rate": round(likes / views * 100, 2) if views else 0,
        "published":       snippet.get("publishedAt", "")[:10],
        "upload_hour_utc": _parse_hour(snippet.get("publishedAt", "")),
        "duration_seconds": _parse_duration(dur),
        "title_length":    len(snippet.get("title", "")),
        "url":             f"https://youtube.com/watch?v={video_id}",
    }


def _generate_insights(your_video: dict, competitors: list, topic: str) -> dict:
    """Compare your video against competitor averages and return recommendations."""
    if not competitors:
        return {"error": "No competitor data available."}

    avg_views        = sum(c["views"] for c in competitors) / len(competitors)
    avg_likes        = sum(c["likes"] for c in competitors) / len(competitors)
    avg_engagement   = sum(c["engagement_rate"] for c in competitors) / len(competitors)
    avg_title_length = sum(c["title_length"] for c in competitors) / len(competitors)
    avg_duration     = sum(c["duration_seconds"] for c in competitors) / len(competitors)

    # Most common upload hour among top 3
    top3_hours = [c["upload_hour_utc"] for c in competitors[:3] if c["upload_hour_utc"] is not None]
    best_hour  = max(set(top3_hours), key=top3_hours.count) if top3_hours else None

    top_competitor = competitors[0]

    recommendations = []

    # Title length
    if your_video.get("title_length", 0) > avg_title_length + 10:
        recommendations.append(
            f"Shorten your title — competitors average {avg_title_length:.0f} chars, yours is {your_video.get('title_length')}."
        )
    elif your_video.get("title_length", 0) < avg_title_length - 10:
        recommendations.append(
            f"Lengthen your title — competitors average {avg_title_length:.0f} chars, yours is {your_video.get('title_length')}."
        )

    # Upload hour
    if best_hour is not None and your_video.get("upload_hour_utc") != best_hour:
        recommendations.append(
            f"Upload at {best_hour:02d}:00 UTC — that's when top competitors post."
        )

    # Duration
    if your_video.get("duration_seconds", 0) > avg_duration + 30:
        recommendations.append(
            f"Trim your video — competitors average {avg_duration:.0f}s, yours is {your_video.get('duration_seconds')}s."
        )

    # Views gap
    if your_video.get("views", 0) < avg_views * 0.5:
        gap = avg_views - your_video.get("views", 0)
        recommendations.append(
            f"Your video has {your_video.get('views', 0):,} views vs competitor avg {avg_views:,.0f} — {gap:,.0f} view gap to close."
        )

    return {
        "competitor_avg_views":      round(avg_views),
        "competitor_avg_engagement": round(avg_engagement, 2),
        "competitor_avg_title_length": round(avg_title_length),
        "competitor_avg_duration_seconds": round(avg_duration),
        "best_upload_hour_utc":      best_hour,
        "top_competitor_title":      top_competitor["title"],
        "top_competitor_views":      top_competitor["views"],
        "top_competitor_url":        top_competitor["url"],
        "recommendations":           recommendations,
    }


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_hour(ts_str: str):
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).hour
    except Exception:
        return None


def _parse_duration(duration: str) -> int:
    """Convert ISO 8601 duration (PT1M30S) to seconds."""
    import re
    if not duration:
        return 0
    pattern = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")
    match = pattern.match(duration)
    if not match:
        return 0
    h = int(match.group(1) or 0)
    m = int(match.group(2) or 0)
    s = int(match.group(3) or 0)
    return h * 3600 + m * 60 + s


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    import sys, json
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Claude AI benchmark"
    print(f"Comparing: {topic}\n")
    result = compare_topic(topic)
    print(json.dumps(result, indent=2, default=str))
