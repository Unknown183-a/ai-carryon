# agents_gaming/adaptive_scheduler.py
"""
Phase 4 adaptive scheduling for the Gaming channel — same top-3-peak-hour +
minimum-gap logic as agents_cricket/adaptive_scheduler.py, sourced from
agents_gaming.velocity_agent / agents_gaming.database instead of Firestore.

Usage (called from scheduler_gaming.py before generating):
    from agents_gaming.adaptive_scheduler import should_upload_now_gaming, mark_upload_done_gaming
    ok, reason = should_upload_now_gaming()
    if ok:
        ... run pipeline ...
        mark_upload_done_gaming()
"""

from datetime import datetime, timezone

DEFAULT_HOURS_UTC = [2, 8, 14, 20]  # spread across the day until real data exists
MIN_GAP_HOURS = 2.0  # gaming trends move fast, but still avoid back-to-back spam


def should_upload_now_gaming():
    """Returns (bool, reason_string). Gaming clips are trend-driven the same
    way cricket matches are event-driven — this only ever BLOCKS to enforce
    a minimum gap once real peak-hour data exists, and otherwise stays
    permissive so a viral clip isn't missed because the clock hour didn't
    line up with a learned peak."""
    now = datetime.now(timezone.utc)
    current_hour = now.hour

    try:
        from agents_gaming.velocity_agent import get_peak_hours_gaming
        peak_hours = get_peak_hours_gaming()
        if isinstance(peak_hours, dict) and "error" not in peak_hours:
            total_samples = sum(h["sample_count"] for h in peak_hours.values())
            if total_samples >= 10:
                windows = sorted(
                    [{"hour": h, **stats} for h, stats in peak_hours.items() if stats["sample_count"] >= 2],
                    key=lambda x: x["avg_velocity"], reverse=True,
                )[:3]
                top_hours = [w["hour"] for w in windows]

                gap_ok, gap_reason = _check_gap(now)
                if not gap_ok:
                    return False, gap_reason

                if current_hour in top_hours:
                    return True, f"[gaming] Hour {current_hour:02d}:00 UTC is peak (top-3: {top_hours})"
                return True, f"[gaming] Hour {current_hour:02d}:00 UTC not peak ({top_hours}), but proceeding — trending clips are time-sensitive"
    except Exception as e:
        print(f"[gaming] adaptive scheduler check failed, allowing upload: {e}")

    if current_hour in DEFAULT_HOURS_UTC:
        return True, f"[gaming] Hour {current_hour:02d}:00 UTC matches default schedule {DEFAULT_HOURS_UTC}"
    gap_ok, gap_reason = _check_gap(now)
    if not gap_ok:
        return False, gap_reason
    return True, "[gaming] No peak-hour data yet — proceeding (trend-driven content)"


def _check_gap(now):
    try:
        from agents_gaming.database import db
        if db is None:
            return True, ""
        last_iso = db.get_meta("last_upload_hour_gaming")
        if not last_iso:
            return True, ""
        last_dt = datetime.fromisoformat(last_iso)
        gap_hours = (now - last_dt).total_seconds() / 3600
        if gap_hours < MIN_GAP_HOURS:
            return False, f"[gaming] Only {gap_hours:.1f}h since last upload — need {MIN_GAP_HOURS}h gap"
        return True, ""
    except Exception:
        return True, ""


def mark_upload_done_gaming():
    """Call after a successful gaming upload to enforce the minimum gap."""
    try:
        from agents_gaming.database import db
        if db is None:
            return
        db.set_meta("last_upload_hour_gaming", datetime.now(timezone.utc).isoformat())
    except Exception as e:
        print(f"[gaming] mark_upload_done_gaming failed: {e}")


if __name__ == "__main__":
    ok, reason = should_upload_now_gaming()
    print(f"Should upload now: {ok}\nReason: {reason}")
