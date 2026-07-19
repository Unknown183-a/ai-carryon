"""
close_ab_loop.py — Phase 3 loop closer.

Finds ab_title_tests rows where actual_views_24h is still NULL, matches
them to a real uploaded video, and fills in the real 24h view count.

Matching strategy (in order of preference):
  1. video_id column, if set (new rows, linked at upload time)
  2. winner_title = videos.title (fallback, for older rows predating
     the video_id link — e.g. z8gbJF4tYRY, uploaded before this fix)

Usage:
    python3 agents/close_ab_loop.py           # all channels
    python3 agents/close_ab_loop.py hindi     # one channel only
"""

import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from agents.database import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def close_loop(channel: str = None):
    pending = db.get_pending_ab_tests()

    if not pending:
        logger.info("No pending AB tests to close.")
        return

    logger.info(f"Found {len(pending)} pending AB test(s) to check.")

    updated = 0
    linked_by_id = 0
    linked_by_title = 0
    no_video_match = 0
    too_early = 0
    no_snapshot = 0

    for row in pending:
        winner_title = row["winner_title"]
        row_video_id = row["video_id"]  # may be None for pre-fix rows
        video_row = None
        matched_via = None

        # 1. Prefer video_id if already linked
        if row_video_id:
            candidate = db.get_video(row_video_id)
            if candidate and (not channel or candidate.get("channel") == channel):
                video_row = candidate
                matched_via = "video_id"

        # 2. Fall back to title-matching for older/unlinked rows
        if not video_row:
            candidate = db.get_video_by_title(winner_title, channel=channel)
            if candidate:
                video_row = candidate
                matched_via = "title"

        if not video_row:
            no_video_match += 1
            logger.warning(f"No matching video for title: '{winner_title[:60]}...' — skipping.")
            continue

        video_id = video_row["video_id"]
        upload_time = _parse_ts(video_row["published"])

        if upload_time is None:
            logger.warning(f"Could not parse published time for {video_id} — skipping.")
            continue

        target_time = upload_time + timedelta(hours=24)
        now = datetime.now(timezone.utc)

        if now < target_time:
            too_early += 1
            continue

        actual_views = _get_closest_snapshot_views(video_id, target_time)

        if actual_views is None:
            no_snapshot += 1
            logger.warning(f"No snapshot data for {video_id} — leaving NULL for now.")
            continue

        # Backfill video_id onto the row if it was matched via title
        # (so future runs use the fast path)
        if matched_via == "title" and not row_video_id:
            db.set_ab_test_video_id(row["id"], video_id)

        db.close_ab_test(row["id"], actual_views, now.strftime("%Y-%m-%dT%H:%M:%SZ"))
        updated += 1
        if matched_via == "video_id":
            linked_by_id += 1
        else:
            linked_by_title += 1

        logger.info(f"'{winner_title[:50]}' ({video_id}, matched via {matched_via}): actual_views_24h = {actual_views}")

    logger.info(
        f"Done. Updated {updated} (by video_id: {linked_by_id}, by title: {linked_by_title}) | "
        f"no video match: {no_video_match} | not 24h old yet: {too_early} | no snapshot yet: {no_snapshot}"
    )


def _get_closest_snapshot_views(video_id: str, target_time: datetime):
    rows = db.get_snapshots(video_id)
    if not rows:
        return None

    best = None
    best_diff = None
    for r in rows:
        ts = _parse_ts(r["timestamp"])
        if ts is None:
            continue
        diff = abs((ts - target_time).total_seconds())
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best = r["views"]

    return best


def _parse_ts(ts_raw):
    if ts_raw is None:
        return None
    if isinstance(ts_raw, (int, float)):
        return datetime.fromtimestamp(ts_raw, tz=timezone.utc)

    # Try native ISO parsing first — handles microseconds and +00:00 offsets,
    # e.g. "2026-07-07T11:21:52.292960+00:00" (actual snapshot timestamp format)
    try:
        dt = datetime.fromisoformat(ts_raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        pass

    # Fallback formats for other timestamp styles seen in this codebase
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(ts_raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            continue
    return None


if __name__ == "__main__":
    channel_arg = sys.argv[1] if len(sys.argv) > 1 else None
    close_loop(channel_arg)
