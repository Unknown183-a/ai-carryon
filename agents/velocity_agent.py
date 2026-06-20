"""
velocity_agent.py — Phase 1: View Velocity Analysis & Peak Hour Detection

Reads output/view_history.json and computes:
  - Per-video velocity: views gained per hour at each snapshot interval
  - Peak hour profile: average view velocity aggregated by hour of day (UTC)

Exposes:
  - compute_velocity(view_history: dict) -> dict        # per-video velocity data
  - get_peak_hours(view_history: dict) -> dict          # {hour: avg_velocity}
  - get_best_upload_windows(view_history, top_n=5)      # ranked peak hours
  - load_and_analyse(path="output/view_history.json")   # convenience loader
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timezone


# ─────────────────────────────────────────────
# Core computation
# ─────────────────────────────────────────────

def compute_velocity(view_history: dict) -> dict:
    """
    For every video and every consecutive snapshot pair, calculate:
      - views_gained  : difference in views between the two snapshots
      - hours_elapsed : time gap in hours between snapshots
      - velocity      : views_gained / hours_elapsed  (views per hour)
      - hour_of_day   : UTC hour of the *later* snapshot (when the gain was recorded)

    Returns a dict keyed by video_id:
    {
      "video_id": {
        "title": "...",
        "published": "...",
        "velocity_points": [
          {
            "timestamp": "2026-06-16T13:00:00",
            "hour_of_day": 13,
            "views": 724,
            "views_gained": 15,
            "hours_elapsed": 1.0,
            "velocity": 15.0
          },
          ...
        ],
        "avg_velocity": 12.3,
        "peak_velocity": 45.0,
        "total_snapshots": 48
      }
    }
    """
    result = {}

    for video_id, data in view_history.items():
        snapshots = data.get("snapshots", [])
        if len(snapshots) < 2:
            continue  # need at least 2 points to compute a delta

        velocity_points = []

        for i in range(1, len(snapshots)):
            prev = snapshots[i - 1]
            curr = snapshots[i]

            try:
                t_prev = _parse_ts(prev["timestamp"])
                t_curr = _parse_ts(curr["timestamp"])
            except (KeyError, ValueError):
                continue

            hours_elapsed = (t_curr - t_prev).total_seconds() / 3600
            if hours_elapsed <= 0:
                continue  # guard against duplicate or reversed timestamps

            views_gained = curr.get("views", 0) - prev.get("views", 0)
            # Clamp negatives to 0 (YouTube can remove views during audits)
            views_gained = max(views_gained, 0)

            velocity = views_gained / hours_elapsed

            velocity_points.append({
                "timestamp": curr["timestamp"],
                "hour_of_day": t_curr.hour,
                "views": curr.get("views", 0),
                "likes": curr.get("likes", 0),
                "views_gained": views_gained,
                "hours_elapsed": round(hours_elapsed, 4),
                "velocity": round(velocity, 4),
            })

        if not velocity_points:
            continue

        velocities = [p["velocity"] for p in velocity_points]
        result[video_id] = {
            "title": data.get("title", ""),
            "published": data.get("published", ""),
            "velocity_points": velocity_points,
            "avg_velocity": round(sum(velocities) / len(velocities), 4),
            "peak_velocity": round(max(velocities), 4),
            "total_snapshots": len(snapshots),
        }

    return result


def get_peak_hours(view_history: dict) -> dict:
    """
    Aggregate velocity by hour of day (UTC) across ALL videos.

    Returns:
    {
      0:  {"avg_velocity": 3.2,  "sample_count": 12},
      1:  {"avg_velocity": 2.8,  "sample_count": 10},
      ...
      23: {"avg_velocity": 18.5, "sample_count": 15},
    }
    """
    velocity_data = compute_velocity(view_history)

    hour_buckets = defaultdict(list)

    for video_data in velocity_data.values():
        for point in video_data["velocity_points"]:
            hour_buckets[point["hour_of_day"]].append(point["velocity"])

    peak_hours = {}
    for hour in range(24):
        values = hour_buckets.get(hour, [])
        peak_hours[hour] = {
            "avg_velocity": round(sum(values) / len(values), 4) if values else 0.0,
            "sample_count": len(values),
        }

    return peak_hours


def get_best_upload_windows(view_history: dict, top_n: int = 5) -> list:
    """
    Return the top N upload hours ranked by average view velocity.

    Returns a list of dicts sorted descending by avg_velocity:
    [
      {"hour": 14, "avg_velocity": 22.5, "sample_count": 18},
      ...
    ]
    """
    peak_hours = get_peak_hours(view_history)

    ranked = sorted(
        [
            {"hour": h, **stats}
            for h, stats in peak_hours.items()
            if stats["sample_count"] > 0
        ],
        key=lambda x: x["avg_velocity"],
        reverse=True,
    )

    return ranked[:top_n]


def get_video_velocity_summary(view_history: dict) -> list:
    """
    Return a flat list of all videos with their velocity stats,
    sorted by avg_velocity descending. Useful for the dashboard table.
    """
    velocity_data = compute_velocity(view_history)

    summary = []
    for video_id, data in velocity_data.items():
        summary.append({
            "video_id": video_id,
            "title": data["title"],
            "published": data["published"],
            "avg_velocity": data["avg_velocity"],
            "peak_velocity": data["peak_velocity"],
            "total_snapshots": data["total_snapshots"],
        })

    return sorted(summary, key=lambda x: x["avg_velocity"], reverse=True)


# ─────────────────────────────────────────────
# Convenience loader
# ─────────────────────────────────────────────

def load_and_analyse(path: str = "output/view_history.json") -> dict:
    """
    Load view_history.json from disk and return the full analysis:
    {
      "velocity_data": {...},      # per-video velocity
      "peak_hours": {...},         # {0..23: {avg_velocity, sample_count}}
      "best_upload_windows": [...],# top 5 hours
      "video_summary": [...],      # flat sorted list
      "total_videos_analysed": N,
      "total_velocity_points": N,
    }
    Returns empty structure with an "error" key if file is missing or malformed.
    """
    if not os.path.exists(path):
        return {"error": f"File not found: {path}"}

    try:
        with open(path, "r") as f:
            view_history = json.load(f)
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}"}

    velocity_data = compute_velocity(view_history)
    peak_hours = get_peak_hours(view_history)
    best_windows = get_best_upload_windows(view_history, top_n=5)
    video_summary = get_video_velocity_summary(view_history)

    total_points = sum(
        len(v["velocity_points"]) for v in velocity_data.values()
    )

    return {
        "velocity_data": velocity_data,
        "peak_hours": peak_hours,
        "best_upload_windows": best_windows,
        "video_summary": video_summary,
        "total_videos_analysed": len(velocity_data),
        "total_velocity_points": total_points,
    }


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _parse_ts(ts_str: str) -> datetime:
    """Parse ISO timestamp string to UTC-aware datetime."""
    # Handle both 'Z' suffix and '+00:00' style
    ts_str = ts_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ─────────────────────────────────────────────
# CLI usage (python agents/velocity_agent.py)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "output/view_history.json"
    analysis = load_and_analyse(path)

    if "error" in analysis:
        print(f"Error: {analysis['error']}")
        sys.exit(1)

    print(f"\n✅ Analysed {analysis['total_videos_analysed']} videos "
          f"({analysis['total_velocity_points']} velocity data points)\n")

    print("📈 Top 5 upload windows (UTC hour → avg views/hr):")
    for w in analysis["best_upload_windows"]:
        bar = "█" * int(w["avg_velocity"] / 2)
        print(f"  {w['hour']:02d}:00  {w['avg_velocity']:6.1f} v/hr  "
              f"[n={w['sample_count']:3d}]  {bar}")

    print("\n🎬 Video velocity ranking:")
    for v in analysis["video_summary"][:10]:
        print(f"  {v['avg_velocity']:6.1f} v/hr  |  {v['title'][:60]}")
