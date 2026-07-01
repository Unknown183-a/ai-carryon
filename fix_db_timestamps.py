"""
fix_db_timestamps.py — Patches agents/database.py's get_peak_hours()
to handle mixed naive/aware timestamps safely.
"""
with open("agents/database.py", "r") as f:
    content = f.read()

old = '''        for video_id, data in all_data.items():
            snapshots = data["snapshots"]
            if len(snapshots) < 2:
                continue
            for i in range(1, len(snapshots)):
                prev = snapshots[i-1]
                curr = snapshots[i]
                try:
                    from datetime import datetime as dt
                    t1 = dt.fromisoformat(prev["timestamp"].replace("Z", "+00:00"))
                    t2 = dt.fromisoformat(curr["timestamp"].replace("Z", "+00:00"))
                    hours_elapsed = (t2 - t1).total_seconds() / 3600
                    if hours_elapsed <= 0:
                        continue
                    views_gained = max(curr["views"] - prev["views"], 0)
                    velocity = views_gained / hours_elapsed
                    hour_velocities[t2.hour].append(velocity)
                except Exception:
                    continue'''

new = '''        for video_id, data in all_data.items():
            snapshots = data["snapshots"]
            if len(snapshots) < 2:
                continue
            for i in range(1, len(snapshots)):
                prev = snapshots[i-1]
                curr = snapshots[i]
                try:
                    t1 = _parse_ts_safe(prev["timestamp"])
                    t2 = _parse_ts_safe(curr["timestamp"])
                    hours_elapsed = (t2 - t1).total_seconds() / 3600
                    if hours_elapsed <= 0:
                        continue
                    views_gained = max(curr["views"] - prev["views"], 0)
                    velocity = views_gained / hours_elapsed
                    hour_velocities[t2.hour].append(velocity)
                except Exception:
                    continue'''

if old not in content:
    print("WARNING: exact block not found — will need manual check")
else:
    content = content.replace(old, new)
    print("Patched get_peak_hours() loop")

helper = '''

def _parse_ts_safe(ts_str):
    """
    Parse a timestamp that may be naive or timezone-aware, always
    return a timezone-AWARE UTC datetime. This fixes the bug where
    some snapshots were saved with utcnow() (naive) and others with
    datetime.now(timezone.utc) (aware), causing subtraction to fail.
    """
    from datetime import datetime as _dt, timezone as _tz
    s = ts_str.replace("Z", "+00:00")
    parsed = _dt.fromisoformat(s)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_tz.utc)
    return parsed
'''

marker = "from contextlib import contextmanager"
if marker in content and "_parse_ts_safe" not in content.split(marker)[0]:
    content = content.replace(marker, marker + helper, 1)
    print("Inserted _parse_ts_safe() helper")
else:
    print("Helper insertion skipped (marker not found or already present)")

with open("agents/database.py", "w") as f:
    f.write(content)

print("Done — wrote agents/database.py")
