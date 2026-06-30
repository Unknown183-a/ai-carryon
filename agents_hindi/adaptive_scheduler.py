"""
agents_hindi/adaptive_scheduler.py — Phase 4 for Hindi Channel

Uses Hindi-only velocity data to determine the best upload hour
for the Hindi channel — completely separate from English timing.
"""

import time
import datetime


def get_best_upload_hour_hindi():
    """Get best upload hour from Hindi velocity data."""
    try:
        from agents_hindi.velocity_agent import get_best_upload_hour_hindi as _get
        return _get()
    except Exception as e:
        print(f"Could not get Hindi best upload hour: {e}")
        return None


def wait_for_best_hour_hindi(log_fn=print):
    """Wait until the best Hindi upload hour, if data is available."""
    best_hour = get_best_upload_hour_hindi()

    if best_hour is None:
        log_fn("No Hindi peak hour data yet — uploading now.")
        return

    now_utc = datetime.datetime.utcnow()
    if now_utc.hour == best_hour:
        log_fn(f"Already in Hindi best upload hour ({best_hour:02d}:00 UTC).")
        return

    target = now_utc.replace(hour=best_hour, minute=0, second=0, microsecond=0)
    if target < now_utc:
        target += datetime.timedelta(days=1)

    wait_seconds = (target - now_utc).total_seconds()

    if wait_seconds > 3600:
        log_fn(f"Hindi best hour is {best_hour:02d}:00 UTC — too far away, uploading now.")
        return

    log_fn(f"Waiting {int(wait_seconds)}s for Hindi best upload hour {best_hour:02d}:00 UTC…")
    time.sleep(wait_seconds)


if __name__ == "__main__":
    hour = get_best_upload_hour_hindi()
    print(f"Best Hindi upload hour: {hour}")
