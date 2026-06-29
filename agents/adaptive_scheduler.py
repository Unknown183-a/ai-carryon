"""
agents/adaptive_scheduler.py — Phase 4: Adaptive Upload Scheduling

Analyzes real view velocity data from SQLite to find the best hour
to upload. Replaces the fixed 5-hour interval with intelligence.

Usage:
    from agents.adaptive_scheduler import get_optimal_upload_time, should_upload_now
"""

import os
from datetime import datetime, timezone, timedelta


def get_peak_hours_analysis():
    """
    Get peak hours from SQLite DB.
    Falls back to velocity_agent JSON method if DB not ready.
    """
    try:
        from agents.database import db
        peak_hours = db.get_peak_hours()
        total_samples = sum(h["sample_count"] for h in peak_hours.values())
        if total_samples >= 10:
            return peak_hours, "db"
    except Exception as e:
        print(f"DB peak hours error: {e}")

    # Fallback to velocity_agent JSON method
    try:
        from agents.velocity_agent import load_and_analyse
        analysis = load_and_analyse("output/view_history.json")
        peak_hours = analysis.get("peak_hours", {})
        return peak_hours, "json"
    except Exception as e:
        print(f"Velocity agent error: {e}")

    return {}, "none"


def get_best_upload_windows(top_n=5):
    """Return top N upload hours by avg velocity."""
    peak_hours, source = get_peak_hours_analysis()
    if not peak_hours:
        return [], source

    windows = [
        {
            "hour": int(h),
            "avg_velocity": data["avg_velocity"],
            "sample_count": data["sample_count"],
        }
        for h, data in peak_hours.items()
        if data["sample_count"] >= 2
    ]

    windows.sort(key=lambda x: x["avg_velocity"], reverse=True)
    return windows[:top_n], source


def get_optimal_upload_hour():
    """
    Return the single best UTC hour to upload.
    Returns None if not enough data (< 3 samples in best window).
    """
    try:
        from agents.database import db
        hour = db.get_best_upload_hour()
        if hour is not None:
            return hour
    except Exception:
        pass

    # Fallback
    windows, _ = get_best_upload_windows(top_n=1)
    if windows and windows[0]["sample_count"] >= 3:
        return windows[0]["hour"]
    return None


def should_upload_now(tolerance_minutes=30):
    """
    Check if current time is within tolerance_minutes of the optimal hour.
    Returns (bool, reason_string).
    """
    best_hour = get_optimal_upload_hour()
    now_utc = datetime.now(timezone.utc)

    if best_hour is None:
        return True, "Not enough data yet — uploading immediately"

    current_hour = now_utc.hour
    current_minute = now_utc.minute

    # Check if we're within tolerance of the best hour
    minutes_into_hour = current_minute
    minutes_until_best = ((best_hour - current_hour) % 24) * 60 - minutes_into_hour

    if minutes_until_best <= 0 or minutes_until_best <= tolerance_minutes:
        return True, f"At or near best upload hour {best_hour:02d}:00 UTC"

    if minutes_until_best > 60 * 6:
        # More than 6 hours away — don't wait, upload now
        return True, f"Best hour {best_hour:02d}:00 UTC is too far — uploading now"

    return False, f"Wait {minutes_until_best} min for best hour {best_hour:02d}:00 UTC"


def wait_for_optimal_time(max_wait_minutes=90, log_fn=None):
    """
    Wait until optimal upload time if it's within max_wait_minutes.
    Calls log_fn(msg) for progress updates.
    """
    import time

    if log_fn is None:
        log_fn = print

    best_hour = get_optimal_upload_hour()
    if best_hour is None:
        log_fn("Adaptive scheduler: no peak hour data yet, uploading immediately")
        return

    now_utc = datetime.now(timezone.utc)
    target = now_utc.replace(hour=best_hour, minute=0, second=0, microsecond=0)

    if target < now_utc:
        target += timedelta(days=1)

    wait_seconds = (target - now_utc).total_seconds()

    if wait_seconds <= 0 or wait_seconds > max_wait_minutes * 60:
        log_fn(
            f"Adaptive scheduler: best hour is {best_hour:02d}:00 UTC "
            f"({wait_seconds/60:.0f} min away) — uploading now"
        )
        return

    log_fn(
        f"Adaptive scheduler: waiting {wait_seconds/60:.0f} min "
        f"for best upload window {best_hour:02d}:00 UTC"
    )
    time.sleep(wait_seconds)
    log_fn(f"Adaptive scheduler: reached {best_hour:02d}:00 UTC — uploading now")


def get_schedule_recommendation():
    """
    Return a human-readable scheduling recommendation.
    Used by dashboard.
    """
    windows, source = get_best_upload_windows(top_n=3)
    best_hour = get_optimal_upload_hour()

    if not windows:
        return {
            "status": "insufficient_data",
            "message": "Need more view snapshots to detect peak hours. Keep running hourly tracking.",
            "best_hour": None,
            "windows": [],
            "source": source,
        }

    top = windows[0]
    ist_hour = (top["hour"] + 5) % 24
    ist_min = 30 if top["hour"] + 5 >= 24 or (top["hour"] + 5) % 24 != (top["hour"] + 5 + 0.5) % 24 else 0
    ist_label = f"{ist_hour:02d}:30 IST" if True else f"{ist_hour:02d}:00 IST"

    return {
        "status": "ready",
        "message": (
            f"Best upload window: {top['hour']:02d}:00 UTC (~{ist_hour:02d}:30 IST). "
            f"Avg velocity: {top['avg_velocity']:.1f} views/hr from {top['sample_count']} samples."
        ),
        "best_hour": best_hour,
        "windows": windows,
        "source": source,
    }


if __name__ == "__main__":
    print("Adaptive Scheduler Analysis")
    print("=" * 40)
    rec = get_schedule_recommendation()
    print(f"Status: {rec['status']}")
    print(f"Message: {rec['message']}")
    print()
    print("Top upload windows:")
    for w in rec["windows"]:
        ist = (w["hour"] + 5) % 24
        print(f"  {w['hour']:02d}:00 UTC (~{ist:02d}:30 IST) — {w['avg_velocity']:.1f} views/hr ({w['sample_count']} samples)")
