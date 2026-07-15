# agents_cricket/velocity_agent.py
"""
Phase 1 velocity analysis for the Cricket channel — same math as
agents/velocity_agent.py and agents_hindi/velocity_agent.py, but sources
data from Supabase Postgres (agents_cricket.database) instead of SQLite,
since cricket runs on Render's free tier with no persistent disk.

Exposes the same function names/shapes as the Hindi module so
pages/peak_hours.py and pages/schedule.py can add cricket as a third
option with minimal branching.
"""

from datetime import datetime, timezone
from collections import defaultdict


def _parse_ts(ts_str: str) -> datetime:
    ts_str = ts_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def compute_velocity_cricket():
    """Compute per-video velocity for the cricket channel.
    Returns {"error": "..."} if the cricket DB isn't reachable in this environment."""
    from agents_cricket.database import db, db_init_error

    if db is None:
        return {"error": f"Cricket DB unavailable: {db_init_error}"}

    try:
        all_data = db.get_all_snapshots()
    except Exception as e:
        return {"error": f"Cricket DB query failed: {e}"}

    result = {}
    for video_id, data in all_data.items():
        snapshots = data.get("snapshots", [])
        if len(snapshots) < 2:
            continue

        velocity_points = []
        for i in range(1, len(snapshots)):
            prev, curr = snapshots[i - 1], snapshots[i]
            try:
                t_prev = _parse_ts(prev["timestamp"])
                t_curr = _parse_ts(curr["timestamp"])
            except (KeyError, ValueError):
                continue

            hours_elapsed = (t_curr - t_prev).total_seconds() / 3600
            if hours_elapsed <= 0:
                continue

            views_gained = max(curr.get("views", 0) - prev.get("views", 0), 0)
            velocity = views_gained / hours_elapsed

            velocity_points.append({
                "timestamp": curr["timestamp"],
                "hour_of_day": t_curr.hour,
                "views": curr.get("views", 0),
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


def get_peak_hours_cricket():
    velocity_data = compute_velocity_cricket()
    if "error" in velocity_data:
        return velocity_data

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


def get_best_upload_windows_cricket(top_n=5):
    peak_hours = get_peak_hours_cricket()
    if isinstance(peak_hours, dict) and "error" in peak_hours:
        return []
    ranked = sorted(
        [{"hour": h, **stats} for h, stats in peak_hours.items() if stats["sample_count"] > 0],
        key=lambda x: x["avg_velocity"],
        reverse=True,
    )
    return ranked[:top_n]


def get_best_upload_hour_cricket():
    windows = get_best_upload_windows_cricket(top_n=1)
    if windows and windows[0]["sample_count"] >= 3:
        return windows[0]["hour"]
    return None


def get_video_velocity_summary_cricket():
    velocity_data = compute_velocity_cricket()
    if "error" in velocity_data:
        return []
    summary = [
        {
            "video_id": vid,
            "title": data["title"],
            "published": data["published"],
            "avg_velocity": data["avg_velocity"],
            "peak_velocity": data["peak_velocity"],
            "total_snapshots": data["total_snapshots"],
        }
        for vid, data in velocity_data.items()
    ]
    return sorted(summary, key=lambda x: x["avg_velocity"], reverse=True)


def load_and_analyse_cricket():
    velocity_data = compute_velocity_cricket()
    if "error" in velocity_data:
        return {"error": velocity_data["error"]}

    peak_hours = get_peak_hours_cricket()
    best_windows = get_best_upload_windows_cricket(top_n=5)
    video_summary = get_video_velocity_summary_cricket()
    total_points = sum(len(v["velocity_points"]) for v in velocity_data.values())

    return {
        "velocity_data": velocity_data,
        "peak_hours": peak_hours,
        "best_upload_windows": best_windows,
        "video_summary": video_summary,
        "total_videos_analysed": len(velocity_data),
        "total_velocity_points": total_points,
    }


if __name__ == "__main__":
    analysis = load_and_analyse_cricket()
    if "error" in analysis:
        print(f"Error: {analysis['error']}")
    else:
        print(f"Cricket videos analysed: {analysis['total_videos_analysed']}")
        print(f"Cricket data points: {analysis['total_velocity_points']}")
        print("\nBest cricket upload windows:")
        for w in analysis["best_upload_windows"]:
            print(f"  {w['hour']:02d}:00 UTC — {w['avg_velocity']:.1f} views/hr ({w['sample_count']} samples)")
