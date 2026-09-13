# agents_cricket/adaptive_scheduler.py
"""
agents_cricket/adaptive_scheduler.py — Phase 4 for the Cricket Channel

agents/adaptive_scheduler.py already has a "cricket" branch in
should_upload_now_for_channel(), but it reads peak-hour data from
agents.database (SQLite) — and cricket view snapshots are written to
Firestore via agents_cricket.database, not SQLite. That branch was
therefore always falling through to the hardcoded default hours
([4, 10, 16] UTC) and never actually learning from real cricket data.

This module is the fix: same top-3-peak-hour + 1-hour-gap logic, but
sourced from agents_cricket.velocity_agent (Firestore) and with gap
tracking stored in cricket_db's meta collection, so it's self-contained
within the cricket channel's own data store.

Usage (call from scheduler_cricket.py before generating):
    from agents_cricket.adaptive_scheduler import should_upload_now_cricket, mark_upload_done_cricket
    ok, reason = should_upload_now_cricket()
    if ok:
        ... run pipeline ...
        mark_upload_done_cricket()
"""

from datetime import datetime, timezone

DEFAULT_HOURS_UTC = [4, 10, 16]  # ~9:30am / 3:30pm / 9:30pm IST — matches
                                  # the fallback already used in agents/adaptive_scheduler.py
MIN_GAP_HOURS = 1.0


def should_upload_now_cricket():
    """Returns (bool, reason_string). Matches are event-driven (a finished/
    live match won't wait for a clock hour), so this is intentionally
    permissive: it blocks uploads only to enforce a minimum gap once
    real peak-hour data exists, and otherwise falls back to 'always allow'
    rather than silently missing a breaking match because the clock hour
    didn't line up."""
    now = datetime.now(timezone.utc)
    current_hour = now.hour

    try:
        from agents_cricket.velocity_agent import get_peak_hours_cricket
        peak_hours = get_peak_hours_cricket()
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
                    return True, f"[cricket] Hour {current_hour:02d}:00 UTC is peak (top-3: {top_hours})"
                # Not a learned peak hour, but still allow — see docstring.
                return True, f"[cricket] Hour {current_hour:02d}:00 UTC not peak ({top_hours}), but proceeding — matches are event-driven"
    except Exception as e:
        print(f"[cricket] adaptive scheduler check failed, allowing upload: {e}")

    # No usable data yet — allow, matching the "not enough data" fallback
    # behaviour of agents/adaptive_scheduler.get_optimal_upload_hour().
    if current_hour in DEFAULT_HOURS_UTC:
        return True, f"[cricket] Hour {current_hour:02d}:00 UTC matches default schedule {DEFAULT_HOURS_UTC}"
    gap_ok, gap_reason = _check_gap(now)
    if not gap_ok:
        return False, gap_reason
    return True, "[cricket] No peak-hour data yet — proceeding (event-driven content)"


def _check_gap(now):
    try:
        from agents_cricket.database import db
        if db is None:
            return True, ""
        last_iso = db.get_meta("last_upload_hour_cricket")
        if not last_iso:
            return True, ""
        last_dt = datetime.fromisoformat(last_iso)
        gap_hours = (now - last_dt).total_seconds() / 3600
        if gap_hours < MIN_GAP_HOURS:
            return False, f"[cricket] Only {gap_hours:.1f}h since last upload — need {MIN_GAP_HOURS}h gap"
        return True, ""
    except Exception:
        return True, ""


def mark_upload_done_cricket():
    """Call after a successful cricket upload to enforce the minimum gap."""
    try:
        from agents_cricket.database import db
        if db is None:
            return
        db.set_meta("last_upload_hour_cricket", datetime.now(timezone.utc).isoformat())
    except Exception as e:
        print(f"[cricket] mark_upload_done_cricket failed: {e}")


if __name__ == "__main__":
    ok, reason = should_upload_now_cricket()
    print(f"Should upload now: {ok}\nReason: {reason}")
