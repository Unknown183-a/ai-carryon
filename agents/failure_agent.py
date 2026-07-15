"""
failure_agent.py — Phase 5: Failure Intelligence.

Reads closed-loop AB test data (ab_title_tests joined with videos, where
actual_views_24h has already been filled in by close_ab_loop.py) and
identifies underperforming videos, then correlates failures against
title pattern to surface which patterns are quietly underperforming.

Read-only: does not write to the database. Prints a report to stdout
and writes a JSON summary to output/failure_report.json for the
dashboard to pick up later.

Usage:
    python3 agents/failure_agent.py           # all channels
    python3 agents/failure_agent.py hindi     # one channel only
"""

import sqlite3
import os
import sys
import json
import logging
import statistics
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "output/aicarryon.db")
REPORT_PATH = os.environ.get("FAILURE_REPORT_PATH", "output/failure_report.json")

FAILURE_PERCENTILE = 0.25
MIN_SAMPLES_FOR_CHANNEL = 5


def analyze(channel=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    query = """
        SELECT t.id, t.topic, t.winner_title, t.winner_pattern, t.winner_score,
               t.actual_views_24h, t.video_id, v.channel, v.published
        FROM ab_title_tests t
        JOIN videos v ON v.video_id = t.video_id
        WHERE t.actual_views_24h IS NOT NULL
    """
    params = []
    if channel:
        query += " AND v.channel = ?"
        params.append(channel)

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        logger.info("No closed-loop AB test data yet (actual_views_24h all NULL). Nothing to analyze.")
        logger.info("Run agents/close_ab_loop.py first, and make sure videos are >=24h old with snapshot data.")
        return

    by_channel = {}
    for r in rows:
        by_channel.setdefault(r["channel"], []).append(r)

    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "channels": {},
    }

    for ch, ch_rows in by_channel.items():
        if len(ch_rows) < MIN_SAMPLES_FOR_CHANNEL:
            logger.info(
                f"[{ch}] only {len(ch_rows)} closed-loop sample(s) -- too thin to trust "
                f"pattern stats (need {MIN_SAMPLES_FOR_CHANNEL}+). Listing raw data only."
            )
            report["channels"][ch] = {
                "sample_size": len(ch_rows),
                "status": "insufficient_data",
                "raw": [_row_summary(r) for r in ch_rows],
            }
            continue

        views = sorted(r["actual_views_24h"] for r in ch_rows)
        median_views = statistics.median(views)
        cutoff_index = max(1, int(len(views) * FAILURE_PERCENTILE))
        failure_cutoff = views[cutoff_index - 1]

        failures = [r for r in ch_rows if r["actual_views_24h"] <= failure_cutoff]
        successes = [r for r in ch_rows if r["actual_views_24h"] > failure_cutoff]

        pattern_stats = _pattern_breakdown(ch_rows, failures)

        logger.info(
            f"[{ch}] {len(ch_rows)} closed-loop videos | median views: {median_views:.0f} | "
            f"failure cutoff (bottom {int(FAILURE_PERCENTILE * 100)}%): <= {failure_cutoff}"
        )
        for pattern, stats in sorted(pattern_stats.items(), key=lambda x: -x[1]["failure_rate"]):
            logger.info(
                f"    pattern={pattern:12s} n={stats['n']:2d}  "
                f"failure_rate={stats['failure_rate']:.0%}  avg_views={stats['avg_views']:.0f}"
            )

        logger.info(f"    Failed videos ({len(failures)}):")
        for r in failures:
            title = (r["winner_title"] or "")[:55]
            topic = (r["topic"] or "")[:40]
            logger.info(
                f"      - '{title}' pattern={r['winner_pattern']} "
                f"views={r['actual_views_24h']} topic={topic}"
            )

        report["channels"][ch] = {
            "sample_size": len(ch_rows),
            "status": "analyzed",
            "median_views": median_views,
            "failure_cutoff": failure_cutoff,
            "pattern_failure_rate": pattern_stats,
            "failures": [_row_summary(r) for r in failures],
            "successes_sample": [_row_summary(r) for r in successes[:5]],
        }

    os.makedirs(os.path.dirname(REPORT_PATH) or ".", exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Report written to {REPORT_PATH}")


def _pattern_breakdown(all_rows, failure_rows):
    failure_ids = {r["id"] for r in failure_rows}
    by_pattern = {}
    for r in all_rows:
        p = r["winner_pattern"] or "unknown"
        d = by_pattern.setdefault(p, {"n": 0, "failures": 0, "views_sum": 0})
        d["n"] += 1
        d["views_sum"] += r["actual_views_24h"]
        if r["id"] in failure_ids:
            d["failures"] += 1

    return {
        p: {
            "n": d["n"],
            "failure_rate": d["failures"] / d["n"],
            "avg_views": d["views_sum"] / d["n"],
        }
        for p, d in by_pattern.items()
    }


def _row_summary(r):
    return {
        "id": r["id"],
        "video_id": r["video_id"],
        "title": r["winner_title"],
        "pattern": r["winner_pattern"],
        "score": r["winner_score"],
        "topic": r["topic"],
        "actual_views_24h": r["actual_views_24h"],
    }


if __name__ == "__main__":
    channel_arg = sys.argv[1] if len(sys.argv) > 1 else None
    analyze(channel_arg)
