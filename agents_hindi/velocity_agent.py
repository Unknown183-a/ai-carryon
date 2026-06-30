"""
agents_hindi/velocity_agent.py — Phase 1 for Hindi Channel

Same velocity analysis as English, but reads only channel="hindi"
data from the shared SQLite database. Keeps Hindi learning separate
from English learning.
"""

from datetime import datetime


def _parse_ts(ts_str: str) -> datetime:
    ts_str = ts_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        from datetime import timezone
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def compute_velocity_hindi():
    """Compute per-video velocity for Hindi channel only."""
    from agents.database import db

    all_data = db.get_all_snapshots()
    result = {}

    for video_id, data in all_data.items():
        if data.get("channel") != "hindi":
            continue

        snapshots = data.get("snapshots", [])
        if len(snapshots) < 2:
            continue

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


def get_peak_hours_hindi():
    """Aggregate velocity by hour of day for Hindi channel only."""
    from collections import defaultdict

    velocity_data = compute_velocity_hindi()
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


def get_best_upload_windows_hindi(top_n=5):
    peak_hours = get_peak_hours_hindi()
    ranked = sorted(
        [{"hour": h, **stats} for h, stats in peak_hours.items() if stats["sample_count"] > 0],
        key=lambda x: x["avg_velocity"],
        reverse=True,
    )
    return ranked[:top_n]


def get_best_upload_hour_hindi():
    windows = get_best_upload_windows_hindi(top_n=1)
    if windows and windows[0]["sample_count"] >= 3:
        return windows[0]["hour"]
    return None


def load_and_analyse_hindi():
    velocity_data = compute_velocity_hindi()
    peak_hours = get_peak_hours_hindi()
    best_windows = get_best_upload_windows_hindi(top_n=5)

    total_points = sum(len(v["velocity_points"]) for v in velocity_data.values())

    return {
        "velocity_data": velocity_data,
        "peak_hours": peak_hours,
        "best_upload_windows": best_windows,
        "total_videos_analysed": len(velocity_data),
        "total_velocity_points": total_points,
    }


if __name__ == "__main__":
    import json
    analysis = load_and_analyse_hindi()
    print(f"Hindi videos analysed: {analysis['total_videos_analysed']}")
    print(f"Hindi data points: {analysis['total_velocity_points']}")
    print("\nBest Hindi upload windows:")
    for w in analysis["best_upload_windows"]:
        print(f"  {w['hour']:02d}:00 UTC — {w['avg_velocity']:.1f} views/hr ({w['sample_count']} samples)")
